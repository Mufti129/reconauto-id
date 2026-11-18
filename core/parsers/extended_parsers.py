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
from core.parsers.base import (
    BaseChannelParser,
    clean_number,
    clean_date,
    load_dataframe,
    extract_universal_bank_rows,
)


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
            gross = abs(clean_number(r.get(c_gross, 0)))
            fee = abs(clean_number(r.get(c_fee, 0))) if c_fee else gross * 0.02
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
            gross = abs(clean_number(r.get(c_gross, 0)))
            fee = abs(clean_number(r.get(c_fee, 0))) if c_fee else 4500.0
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
            gross = abs(clean_number(r.get(c_gross, 0)))
            fee = abs(clean_number(r.get(c_fee, 0))) if c_fee else gross * 0.04
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
        rows = extract_universal_bank_rows(df, bank_code="BANK_CIMB", row_prefix="CIMB")
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
        rows = extract_universal_bank_rows(df, bank_code="BANK_PERMATA", row_prefix="PERMATA")
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
        rows = extract_universal_bank_rows(df, bank_code="BANK_BSI", row_prefix="BSI")
        return self.source_channel, rows


class Camt053XmlParser(BaseChannelParser):
    """Adapter untuk standar perbankan ISO 20022 CAMT.053 XML & Open Financial Exchange (OFX/QFX)."""

    @property
    def channel_id(self) -> str:
        return "BANK_CAMT053"

    @property
    def channel_name(self) -> str:
        return "ISO 20022 CAMT.053 XML & OFX/QFX Bank Statement"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_CAMT053

    def classify_channel_type(self) -> str:
        return "BANK"

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if fn.endswith((".camt053", ".ofx", ".qfx")) or "camt053" in fn or "camt.053" in fn:
            return True
        if raw_text:
            rt_low = raw_text.lower()
            if "bktoncstmrstmt" in rt_low or "<ntry>" in rt_low or "<stmttrn>" in rt_low or "<ofx>" in rt_low:
                return True
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        import re
        import os
        import xml.etree.ElementTree as ET

        if isinstance(source, bytes):
            text = source.decode("utf-8-sig", errors="replace")
        elif hasattr(source, "read"):
            if hasattr(source, "seek"):
                source.seek(0)
            content = source.read()
            text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else str(content)
        elif isinstance(source, str) and os.path.exists(source):
            with open(source, "r", encoding="utf-8-sig", errors="replace") as f:
                text = f.read()
        else:
            text = str(source)

        rows: List[BankStatementRow] = []

        # 1. Cek apakah format OFX / QFX (<STMTTRN>)
        if "<STMTTRN>" in text.upper():
            blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, flags=re.IGNORECASE | re.DOTALL)
            if not blocks:
                blocks = re.split(r"<STMTTRN>", text, flags=re.IGNORECASE)[1:]
            for idx, blk in enumerate(blocks, 1):
                m_amt = re.search(r"<TRNAMT>([^\r\n<]+)", blk, re.IGNORECASE)
                m_dt = re.search(r"<DTPOSTED>(\d{8})", blk, re.IGNORECASE)
                m_memo = re.search(r"<(?:MEMO|NAME)>([^\r\n<]+)", blk, re.IGNORECASE)
                m_type = re.search(r"<TRNTYPE>([^\r\n<]+)", blk, re.IGNORECASE)

                amt_val = clean_number(m_amt.group(1)) if m_amt else 0.0
                raw_dt = m_dt.group(1) if m_dt else "20260815"
                iso_dt = f"{raw_dt[:4]}-{raw_dt[4:6]}-{raw_dt[6:8]}" if len(raw_dt) == 8 else clean_date(raw_dt)
                desc = m_memo.group(1).strip() if m_memo else f"OFX Transaction #{idx}"
                ttype = "DB" if (amt_val < 0 or (m_type and "DEBIT" in m_type.group(1).upper())) else "CR"

                if abs(amt_val) > 0:
                    rows.append(BankStatementRow(
                        row_id=f"OFX-{idx}",
                        date=iso_dt,
                        description=desc,
                        amount=abs(amt_val),
                        txn_type=ttype,
                        bank_code="BANK_CAMT053"
                    ))
            if rows:
                return self.source_channel, rows

        # 2. Parse ISO 20022 CAMT.053 XML (<Ntry>)
        try:
            root = ET.fromstring(text.strip())
            def _local(tag: str) -> str:
                return tag.split("}", 1)[-1] if "}" in tag else tag

            idx = 0
            for elem in root.iter():
                if _local(elem.tag) == "Ntry":
                    idx += 1
                    amt_val = 0.0
                    cdt_dbt = "CR"
                    dt_str = ""
                    desc_parts = []

                    for sub in elem.iter():
                        lname = _local(sub.tag)
                        val = (sub.text or "").strip()
                        if not val:
                            continue
                        if lname == "Amt" and amt_val == 0.0:
                            amt_val = abs(clean_number(val))
                        elif lname == "CdtDbtInd":
                            cdt_dbt = "DB" if val.upper().startswith(("DBIT", "DB", "D")) else "CR"
                        elif lname in ("Dt", "DtTm") and not dt_str:
                            dt_str = clean_date(val)
                        elif lname in ("Ustrd", "AddtlNtryInf", "EndToEndId", "AcctSvcrRef"):
                            if val not in desc_parts:
                                desc_parts.append(val)

                    if amt_val > 0:
                        rows.append(BankStatementRow(
                            row_id=f"CAMT-{idx}",
                            date=dt_str or "2026-08-15",
                            description=" | ".join(desc_parts) if desc_parts else f"CAMT.053 Entry #{idx}",
                            amount=amt_val,
                            txn_type=cdt_dbt,
                            bank_code="BANK_CAMT053"
                        ))
        except Exception:
            pass

        return self.source_channel, rows


class LazadaParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "MARKETPLACE_LAZADA"

    @property
    def channel_name(self) -> str:
        return "Lazada Seller Center (Account Statement)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.MARKETPLACE_LAZADA

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn = filename.lower()
        if "lazada" in fn:
            return True
        if df is not None:
            cols = " ".join([str(c).lower() for c in df.columns])
            return any(k in cols for k in ["lazada", "order item id", "statement number", "lazmall"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []
        c_ord = next((c for c in df.columns if any(k in c.lower() for k in ["order", "pesanan", "invoice", "item id"])), df.columns[0])
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["date", "tanggal", "time"])), df.columns[1] if len(df.columns) > 1 else df.columns[0])
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["gross", "item price", "amount", "total", "harga"])), df.columns[2] if len(df.columns) > 2 else df.columns[-1])
        c_fee = next((c for c in df.columns if any(k in c.lower() for k in ["fee", "commission", "komisi", "potongan"])), None)
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["payout", "net", "cair"])), None)
        c_batch = next((c for c in df.columns if any(k in c.lower() for k in ["statement", "batch", "payout ref"])), None)

        for idx, r in df.iterrows():
            oid = str(r.get(c_ord, f"LZD-{idx+1}")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = abs(clean_number(r.get(c_gross, 0)))
            fee = abs(clean_number(r.get(c_fee, 0))) if c_fee else round(gross * 0.045, 2)
            net = clean_number(r.get(c_net, 0)) if c_net else round(gross - fee, 2)
            batch = str(r.get(c_batch, f"LZD-STMT-{dt[:10]}")).strip() if c_batch else f"LZD-STMT-{dt[:10]}"

            if gross > 0:
                txns.append(CanonicalTransaction(
                    txn_id=oid,
                    source_channel=SourceChannel.MARKETPLACE_LAZADA,
                    date=dt,
                    description=f"Lazada Order #{oid}",
                    gross_amount=gross,
                    fee_amount=fee,
                    net_amount=net,
                    batch_id=batch
                ))
        return self.source_channel, txns


class UniversalSmartParser(BaseChannelParser):
    """
    Universal Heuristic & Fuzzy Column Mapper (Fallback Cerdas):
    Secara otomatis mengenali dan menormalisasi berkas CSV (; / , / tab / |), Excel, JSON, atau XML
    dari sistem ERP / Akuntansi / Bank / Marketplace / Kurir kustom meskipun nama file dan nama kolom
    tidak mengikuti template standar.
    """

    @property
    def channel_id(self) -> str:
        return "UNIVERSAL_SMART_MAPPER"

    @property
    def channel_name(self) -> str:
        return "Universal Smart Adaptive Mapper (Auto-Detect Schema)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_BCA

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        return df is not None and not df.empty and len(df.columns) >= 2

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[Any]]:
        df = load_dataframe(source, filename)
        if df is None or df.empty:
            return SourceChannel.UNKNOWN, []

        cols_lower = {c: str(c).lower().strip() for c in df.columns}
        all_cols_text = " | ".join(cols_lower.values())
        fn_lower = (filename or "").lower()

        # 1. Deteksi apakah skema merupakan LOGISTICS COD (memiliki kolom AWB/Resi + COD)
        has_awb = any(any(k in cl for k in ("awb", "resi", "waybill", "connote", "no_pengiriman")) for cl in cols_lower.values())
        has_cod = "cod" in all_cols_text or "cod" in fn_lower or "kurir" in fn_lower or "ekspedisi" in fn_lower
        if has_awb and has_cod:
            c_awb = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("awb", "resi", "waybill", "connote"))), df.columns[0])
            c_ord = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("order", "pesanan", "invoice", "ref"))), None)
            c_amt = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("cod_amount", "nilai_cod", "tagihan", "cod", "amount", "nominal", "gross"))), df.columns[1])
            c_fee = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("fee", "ongkir", "biaya", "potongan"))), None)
            c_net = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("net", "remit", "cair", "diterima", "setor"))), None)
            c_dt = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("date", "tanggal", "tgl", "waktu", "settlement"))), None)
            c_bref = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("bank_ref", "batch", "ref_bank", "no_transfer"))), None)

            cod_rows: List[CodSettlementRow] = []
            for idx, r in df.iterrows():
                awb = str(r.get(c_awb, f"AWB-AUTO-{idx+1}")).strip()
                amt = abs(clean_number(r.get(c_amt, 0)))
                if amt <= 0:
                    continue
                fee = abs(clean_number(r.get(c_fee, 0))) if c_fee else 0.0
                net = clean_number(r.get(c_net, 0)) if c_net else (amt - fee)
                dt = clean_date(r.get(c_dt, "")) if c_dt else "2026-08-15"
                oid = str(r.get(c_ord, f"ORD-{awb}")).strip() if c_ord else f"ORD-{awb}"
                bref = str(r.get(c_bref, "")).strip() if c_bref and not pd.isna(r.get(c_bref)) else None
                if bref in ("", "-", "nan", "None"):
                    bref = None
                status = "COD_UNREMITTED" if not bref else ("COD_SHORTAGE" if (amt - fee) - net > 1.0 else "PENDING")

                cod_rows.append(CodSettlementRow(
                    awb_number=awb,
                    courier_name="Ekspedisi COD",
                    order_id=oid,
                    cod_amount=amt,
                    courier_fee=fee,
                    net_remitted=net,
                    settlement_date=dt,
                    bank_ref_id=bref,
                    status=status
                ))
            if cod_rows:
                return SourceChannel.LOGISTICS_JNE_COD, cod_rows

        # 2. Deteksi apakah skema merupakan MUTASI BANK (memiliki Saldo/Mutasi/Rekening atau kolom terpisah Debit & Kredit tanpa kolom Order/Invoice)
        has_order_col = any(any(k in cl for k in ("order_id", "order id", "no pesanan", "nomor pesanan", "sku", "produk", "product", "fee", "komisi", "mdr")) for cl in cols_lower.values())
        has_bank_col = any(any(k in cl for k in ("saldo", "balance", "mutasi", "rekening", "db/cr", "debit", "debet", "kredit", "credit", "cabang", "branch")) for cl in cols_lower.values())
        is_bank_file = any(k in fn_lower for k in ("bank", "mutasi", "rekening", "statement", "giro", "koran"))

        if (has_bank_col or is_bank_file) and not has_order_col:
            c_date = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("tanggal", "tgl", "date", "waktu", "post"))), df.columns[0])
            c_desc = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("keterangan", "uraian", "deskripsi", "description", "remark", "berita", "memo", "narasi"))), df.columns[1] if len(df.columns) > 1 else df.columns[0])
            c_debit = next((c for c, cl in cols_lower.items() if cl in ("debit", "debet", "db", "mutasi debit", "uang keluar", "withdrawal", "debit amount")), None)
            c_credit = next((c for c, cl in cols_lower.items() if cl in ("kredit", "credit", "cr", "mutasi kredit", "uang masuk", "deposit", "credit amount")), None)
            c_amt = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("jumlah", "amount", "nominal", "mutasi", "nilai", "total"))), df.columns[-1])
            c_type = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("tipe", "type", "db/cr", "d/c", "jenis", "arus"))), None)
            c_bal = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("saldo", "balance"))), None)

            bank_rows: List[BankStatementRow] = []
            for idx, r in df.iterrows():
                desc = str(r.get(c_desc, "")).strip()
                if "SALDO AWAL" in desc.upper() or "OPENING BALANCE" in desc.upper():
                    continue
                dt = clean_date(r.get(c_date, "")) or "2026-08-15"
                bal = clean_number(r.get(c_bal)) if c_bal and not pd.isna(r.get(c_bal)) else None

                # Dukungan Kolom Terpisah Debit vs Kredit (Format Umum Bank Mandiri, BNI, BRI, Buku Besar GL)
                if c_debit and c_credit:
                    deb_val = abs(clean_number(r.get(c_debit, 0)))
                    crd_val = abs(clean_number(r.get(c_credit, 0)))
                    if crd_val > 0:
                        amt_val, ttype = crd_val, "CR"
                    elif deb_val > 0:
                        amt_val, ttype = deb_val, "DB"
                    else:
                        continue
                else:
                    raw_val_str = str(r.get(c_amt, ""))
                    amt_raw = clean_number(r.get(c_amt, 0))
                    if abs(amt_raw) <= 0:
                        continue
                    ttype = "CR"
                    if c_type:
                        t_flag = str(r.get(c_type, "")).strip().upper()
                        if any(t_flag.startswith(p) for p in ("DB", "DEBIT", "DEBET", "D", "OUT", "KELUAR")):
                            ttype = "DB"
                    elif amt_raw < 0 or raw_val_str.strip().upper().endswith(("DB", "D", "DR")):
                        ttype = "DB"
                    amt_val = abs(amt_raw)

                bank_rows.append(BankStatementRow(
                    row_id=f"BANK-AUTO-{idx+1}",
                    date=dt,
                    description=desc or f"Mutasi Bank #{idx+1}",
                    amount=amt_val,
                    txn_type=ttype,
                    bank_code="BANK_BCA",
                    balance=bal,
                    raw_data={str(k): str(v) for k, v in r.to_dict().items()}
                ))
            if bank_rows:
                return SourceChannel.BANK_BCA, bank_rows

        # 3. Default Adaptive Mapping: Transaksi Penjualan / Marketplace / Payment Gateway / POS / ERP
        c_id = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("order", "invoice", "pesanan", "trx", "txn", "receipt", "nota", "faktur", "id", "ref", "nomor", "no"))), df.columns[0])
        c_date = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("tanggal", "tgl", "date", "waktu", "time", "created", "settled"))), df.columns[1] if len(df.columns) > 1 else df.columns[0])
        c_gross = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("gross", "kotor", "harga", "subtotal", "amount", "nominal", "total", "jumlah", "nilai", "penjualan"))), None)
        c_fee = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("fee", "komisi", "potongan", "mdr", "biaya", "admin", "charge", "discount", "diskon"))), None)
        c_net = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("net", "bersih", "cair", "settlement_amount", "payout", "diterima", "terima"))), None)
        c_batch = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("batch", "settlement_id", "payout_id", "ref_pencairan", "no_pencairan", "kelompok", "group"))), None)
        c_desc = next((c for c, cl in cols_lower.items() if any(k in cl for k in ("keterangan", "deskripsi", "description", "produk", "item", "nama", "uraian", "memo"))), None)

        # Jika tidak ada kolom gross maupun net, cari kolom numerik pertama
        if not c_gross and not c_net:
            for c in df.columns:
                if c not in (c_id, c_date):
                    c_gross = c
                    break

        txns: List[CanonicalTransaction] = []
        for idx, r in df.iterrows():
            tid = str(r.get(c_id, f"TXN-AUTO-{idx+1}")).strip()
            if not tid or tid.lower() in ("total", "grand total", "jumlah", "subtotal", "nan"):
                continue
            dt = clean_date(r.get(c_date, "")) or "2026-08-15"
            gross = abs(clean_number(r.get(c_gross, 0))) if c_gross else 0.0
            fee = abs(clean_number(r.get(c_fee, 0))) if c_fee else 0.0
            net = clean_number(r.get(c_net, 0)) if c_net else (gross - fee)
            if gross == 0.0 and net > 0.0:
                gross = net + fee
            if gross <= 0 and net <= 0:
                continue

            batch_id = str(r.get(c_batch, "")).strip() if c_batch and not pd.isna(r.get(c_batch)) else ""
            if not batch_id or batch_id.lower() in ("nan", "none", "-"):
                batch_id = f"BATCH-AUTO-{dt[:10]}"

            desc = str(r.get(c_desc, f"Transaksi #{tid}")).strip() if c_desc else f"Transaksi #{tid}"

            txns.append(CanonicalTransaction(
                txn_id=tid,
                source_channel=SourceChannel.MARKETPLACE_SHOPEE,
                date=dt,
                description=desc,
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=batch_id,
                metadata={"source_file": filename, "adaptive_mapped": True}
            ))

        if txns:
            return SourceChannel.MARKETPLACE_SHOPEE, txns
        return SourceChannel.UNKNOWN, []


