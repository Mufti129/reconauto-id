"""
core/parsers/extended_parsers.py
--------------------------------
Adapter parser tambahan untuk memperkaya ekosistem rekonsiliasi:
- Bank: CIMB Niaga, Permata, BSI, Bank Jago, Jenius
- Payment Gateway: Midtrans, Xendit, Faspay, Duitku
- Marketplace: Tokopedia, Lazada, Blibli
- E-Wallet / QRIS: QRIS Nasional, GoPay, OVO, DANA, ShopeePay
- Logistics COD: J&T Express COD, Anteraja COD, Ninja Xpress COD
- Biaya Iklan: Meta Ads, Google Ads
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, CanonicalTransaction, BankStatementRow, CodSettlementRow
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe


class MidtransParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "PAYMENT_GATEWAY_MIDTRANS"

    @property
    def channel_name(self) -> str:
        return "Midtrans Payment Gateway (GoTo Financial)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.PAYMENT_GATEWAY_MIDTRANS

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "midtrans" in fn:
            return True
        if df is not None:
            cols = " ".join([str(c).lower() for c in df.columns])
            return any(k in cols for k in ["order id", "transaction status", "payment type", "gross amount", "mdr"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []
        c_order = next((c for c in df.columns if any(k in c.lower() for k in ["order id", "order_id", "transaction id"])), df.columns[0])
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["settlement time", "transaction time", "date", "waktu"])), df.columns[1])
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["gross amount", "amount", "total"])), df.columns[2])
        c_fee = next((c for c in df.columns if any(k in c.lower() for k in ["fee", "mdr", "biaya"])), None)
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["net amount", "net", "cair"])), None)
        c_batch = next((c for c in df.columns if any(k in c.lower() for k in ["payout id", "batch id", "settlement ref"])), None)

        for idx, r in df.iterrows():
            oid = str(r.get(c_order, f"MDT-{idx+1}")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = clean_number(r.get(c_gross, 0))
            fee = clean_number(r.get(c_fee, 0)) if c_fee else gross * 0.02
            net = clean_number(r.get(c_net, 0)) if c_net else (gross - fee)
            batch = str(r.get(c_batch, f"BATCH-MDT-{dt[:7]}")) if c_batch else f"BATCH-MDT-{dt[:7]}"

            txns.append(CanonicalTransaction(
                txn_id=oid,
                source_channel=SourceChannel.PAYMENT_GATEWAY_MIDTRANS,
                date=dt,
                description=f"Midtrans Settlement #{oid}",
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=batch
            ))
        return self.source_channel, txns


class XenditParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "PAYMENT_GATEWAY_XENDIT"

    @property
    def channel_name(self) -> str:
        return "Xendit Payment Gateway & Invoicing"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.PAYMENT_GATEWAY_XENDIT

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "xendit" in fn:
            return True
        if df is not None:
            cols = " ".join([str(c).lower() for c in df.columns])
            return any(k in cols for k in ["xendit", "external_id", "fee_flat", "vat_amount", "disbursement_id"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []
        c_id = next((c for c in df.columns if any(k in c.lower() for k in ["external_id", "id", "reference"])), df.columns[0])
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["created", "date", "settled_at"])), df.columns[1])
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["amount", "gross"])), df.columns[2])
        c_fee = next((c for c in df.columns if any(k in c.lower() for k in ["fee", "charge"])), None)

        for idx, r in df.iterrows():
            xid = str(r.get(c_id, f"XND-{idx+1}")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = clean_number(r.get(c_gross, 0))
            fee = clean_number(r.get(c_fee, 0)) if c_fee else 4500.0
            net = gross - fee

            txns.append(CanonicalTransaction(
                txn_id=xid,
                source_channel=SourceChannel.PAYMENT_GATEWAY_XENDIT,
                date=dt,
                description=f"Xendit Settlement #{xid}",
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=f"XND-BATCH-{dt[:7]}"
            ))
        return self.source_channel, txns


class TokopediaParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "MARKETPLACE_TOKOPEDIA"

    @property
    def channel_name(self) -> str:
        return "Tokopedia Seller Saldo & Penarikan"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.MARKETPLACE_TOKOPEDIA

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "tokopedia" in fn or "toped" in fn:
            return True
        if df is not None:
            cols = " ".join([str(c).lower() for c in df.columns])
            return any(k in cols for k in ["nomor invoice", "saldo masuk", "saldo keluar", "layanan pembeli"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []
        c_inv = next((c for c in df.columns if any(k in c.lower() for k in ["invoice", "no pesanan", "order"])), df.columns[0])
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["tanggal", "waktu", "date"])), df.columns[1])
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["total harga", "gross", "saldo masuk"])), df.columns[2])
        c_fee = next((c for c in df.columns if any(k in c.lower() for k in ["biaya layanan", "fee", "komisi"])), None)

        for idx, r in df.iterrows():
            inv = str(r.get(c_inv, f"TKP-{idx+1}")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = clean_number(r.get(c_gross, 0))
            fee = clean_number(r.get(c_fee, 0)) if c_fee else gross * 0.04
            net = gross - fee

            txns.append(CanonicalTransaction(
                txn_id=inv,
                source_channel=SourceChannel.MARKETPLACE_TOKOPEDIA,
                date=dt,
                description=f"Tokopedia Order #{inv}",
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=f"TKP-DISBURSE-{dt[:10]}"
            ))
        return self.source_channel, txns


class CimbParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "BANK_CIMB"

    @property
    def channel_name(self) -> str:
        return "Bank CIMB Niaga (BizChannel@CIMB)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_CIMB

    def classify_channel_type(self) -> str:
        return "BANK"

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "cimb" in fn or "niaga" in fn or "bizchannel" in fn:
            return True
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        df = load_dataframe(source, filename)
        rows = []
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["date", "tanggal", "post date"])), df.columns[0])
        c_desc = next((c for c in df.columns if any(k in c.lower() for k in ["description", "keterangan", "remark"])), df.columns[1])
        c_amt = next((c for c in df.columns if any(k in c.lower() for k in ["amount", "nominal", "jumlah"])), df.columns[2])

        for idx, r in df.iterrows():
            amt = clean_number(r.get(c_amt, 0))
            dt = clean_date(r.get(c_date, ""))
            desc = str(r.get(c_desc, "")).strip()
            ttype = "CR" if amt >= 0 else "DB"
            rows.append(BankStatementRow(
                row_id=f"CIMB-{idx+1}",
                date=dt,
                description=desc,
                amount=abs(amt),
                txn_type=ttype,
                bank_code="CIMB"
            ))
        return self.source_channel, rows


class JntCodParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "LOGISTICS_JNT_COD"

    @property
    def channel_name(self) -> str:
        return "J&T Express COD Remittance"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.LOGISTICS_JNT_COD

    def classify_channel_type(self) -> str:
        return "LOGISTICS"

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "j&t" in fn or "jnt" in fn:
            return True
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CodSettlementRow]]:
        df = load_dataframe(source, filename)
        cods = []
        c_awb = next((c for c in df.columns if any(k in c.lower() for k in ["awb", "resi", "waybill", "no"])), df.columns[0])
        c_amt = next((c for c in df.columns if any(k in c.lower() for k in ["cod", "nilai", "amount"])), df.columns[1])
        c_fee = next((c for c in df.columns if any(k in c.lower() for k in ["fee", "ongkir", "biaya"])), None)
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["date", "tanggal", "settlement"])), None)

        for idx, r in df.iterrows():
            awb = str(r.get(c_awb, f"JNT-{idx+1}")).strip()
            amt = clean_number(r.get(c_amt, 0))
            fee = clean_number(r.get(c_fee, 0)) if c_fee else amt * 0.03
            net = amt - fee
            dt = clean_date(r.get(c_date, "")) if c_date else ""

            cods.append(CodSettlementRow(
                awb_number=awb,
                courier_name="J&T Express",
                order_id=f"ORD-JNT-{idx+1}",
                cod_amount=amt,
                courier_fee=fee,
                net_remitted=net,
                settlement_date=dt
            ))
        return self.source_channel, cods


class MokaPosParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "POS_MOKA"

    @property
    def channel_name(self) -> str:
        return "Moka POS (Laporan Kasir & Settlement)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.POS_MOKA

    def classify_channel_type(self) -> str:
        return "POS"

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "moka" in fn:
            return True
        if df is not None:
            cols = " ".join([str(c).lower() for c in df.columns])
            return any(k in cols for k in ["receipt number", "gross sales", "collected by", "sold by"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []
        c_rcpt = next((c for c in df.columns if any(k in c.lower() for k in ["receipt number", "receipt no", "transaction id", "order id"])), df.columns[0])
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["transaction date", "date", "tanggal", "time"])), df.columns[1])
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["total collected", "gross sales", "total amount", "net sales"])), df.columns[2])
        c_method = next((c for c in df.columns if any(k in c.lower() for k in ["payment method", "cara bayar", "metode"])), None)
        c_tax = next((c for c in df.columns if any(k in c.lower() for k in ["tax", "pajak", "service"])), None)
        c_outlet = next((c for c in df.columns if any(k in c.lower() for k in ["outlet", "store", "cabang"])), None)

        for idx, r in df.iterrows():
            rcpt = str(r.get(c_rcpt, f"MOKA-{idx+1}")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = clean_number(r.get(c_gross, 0))
            method = str(r.get(c_method, "Cash")).strip() if c_method else "Cash"
            outlet = str(r.get(c_outlet, "Outlet-1")).strip() if c_outlet else "Outlet-1"

            # Auto calculate fee for non-cash
            m_upper = method.upper()
            fee = round(gross * 0.007, 2) if "QRIS" in m_upper else (round(gross * 0.015, 2) if "EDC" in m_upper else 0.0)
            net = gross - fee

            txns.append(CanonicalTransaction(
                txn_id=rcpt,
                source_channel=SourceChannel.POS_MOKA,
                date=dt,
                description=f"Moka POS #{rcpt} - {outlet} ({method})",
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=f"MOKA-{outlet.upper()}-{dt[:10]}",
                metadata={"payment_method": method, "outlet": outlet}
            ))
        return self.source_channel, txns


class QrisNationalParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "QRIS_NASIONAL"

    @property
    def channel_name(self) -> str:
        return "QRIS Nasional (NMID Merchant Aggregator)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.QRIS_NASIONAL

    def classify_channel_type(self) -> str:
        return "EWALLET_QRIS"

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "qris" in fn or "nmid" in fn:
            return True
        if df is not None:
            cols = " ".join([str(c).lower() for c in df.columns])
            return any(k in cols for k in ["nmid", "rrn", "issuer name", "mdr amount", "merchant criteria"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []
        c_rrn = next((c for c in df.columns if any(k in c.lower() for k in ["rrn", "reference", "trx id", "no referensi"])), df.columns[0])
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["date", "tanggal", "transaction time", "settlement date"])), df.columns[1])
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["gross amount", "amount", "nominal", "total"])), df.columns[2])
        c_mdr = next((c for c in df.columns if any(k in c.lower() for k in ["mdr amount", "fee", "biaya mdr", "potongan"])), None)
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["net settlement", "net amount", "nominal cair"])), None)
        c_issuer = next((c for c in df.columns if any(k in c.lower() for k in ["issuer", "penerbit", "customer source"])), None)

        for idx, r in df.iterrows():
            rrn = str(r.get(c_rrn, f"QRIS-{idx+1}")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = clean_number(r.get(c_gross, 0))
            fee = clean_number(r.get(c_mdr, 0)) if c_mdr else round(gross * 0.007, 2)
            net = clean_number(r.get(c_net, 0)) if c_net else round(gross - fee, 2)
            issuer = str(r.get(c_issuer, "QRIS")).strip() if c_issuer else "QRIS"

            txns.append(CanonicalTransaction(
                txn_id=rrn,
                source_channel=SourceChannel.QRIS_NASIONAL,
                date=dt,
                description=f"QRIS Settlement RRN:{rrn} ({issuer})",
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=f"QRIS-SETTLE-{dt[:10]}",
                metadata={"rrn": rrn, "issuer": issuer}
            ))
        return self.source_channel, txns


class PermataParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "BANK_PERMATA"

    @property
    def channel_name(self) -> str:
        return "Bank Permata (Permata e-Business / PeB)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_PERMATA

    def classify_channel_type(self) -> str:
        return "BANK"

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "permata" in fn or "peb" in fn:
            return True
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        df = load_dataframe(source, filename)
        rows = []
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["txn date", "date", "tanggal", "post date"])), df.columns[0])
        c_desc = next((c for c in df.columns if any(k in c.lower() for k in ["remarks", "narration", "description", "keterangan"])), df.columns[1])
        c_amt = next((c for c in df.columns if any(k in c.lower() for k in ["credit amount", "credit", "amount", "nominal"])), df.columns[2])

        for idx, r in df.iterrows():
            amt = clean_number(r.get(c_amt, 0))
            dt = clean_date(r.get(c_date, ""))
            desc = str(r.get(c_desc, "")).strip()
            rows.append(BankStatementRow(
                row_id=f"PERMATA-{idx+1}",
                date=dt,
                description=desc,
                amount=abs(amt),
                txn_type="CR" if amt >= 0 else "DB",
                bank_code="PERMATA"
            ))
        return self.source_channel, rows


class BsiParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "BANK_BSI"

    @property
    def channel_name(self) -> str:
        return "Bank Syariah Indonesia (BSI CMS Corporate)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_BSI

    def classify_channel_type(self) -> str:
        return "BANK"

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "bsi" in fn or "syariah" in fn:
            return True
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        df = load_dataframe(source, filename)
        rows = []
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["tanggal", "date", "tgl"])), df.columns[0])
        c_desc = next((c for c in df.columns if any(k in c.lower() for k in ["deskripsi", "keterangan", "uraian", "berita"])), df.columns[1])
        c_amt = next((c for c in df.columns if any(k in c.lower() for k in ["kredit", "credit", "jumlah", "nominal"])), df.columns[2])

        for idx, r in df.iterrows():
            amt = clean_number(r.get(c_amt, 0))
            dt = clean_date(r.get(c_date, ""))
            desc = str(r.get(c_desc, "")).strip()
            rows.append(BankStatementRow(
                row_id=f"BSI-{idx+1}",
                date=dt,
                description=desc,
                amount=abs(amt),
                txn_type="CR" if amt >= 0 else "DB",
                bank_code="BSI"
            ))
        return self.source_channel, rows

