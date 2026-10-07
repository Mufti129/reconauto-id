"""
core/parsers/pos/jubelio_parser.py
-----------------------------------
Adapter parser untuk laporan transaksi penjualan dan ekspor pesanan Jubelio (Jubelio POS & Omnichannel).

Format laporan ekspor Jubelio POS umumnya berformat Excel (.xlsx) atau CSV dengan kolom-kolom:
- No. Pesanan / SO Number / No. Transaksi (misal: SO-20240101-0001, POS-001)
- No. Referensi / No. Invoice (Nomor referensi pembayaran EDC/QRIS/struk)
- Tanggal Pesanan / Tanggal Transaksi
- Toko / Lokasi / Cabang (misal: Store Jakarta Pusat, Outlet Surabaya)
- Kasir / User / Sales Person
- Metode Pembayaran (Tunai, EDC BCA, EDC Mandiri, QRIS, Transfer, Marketplace)
- Grand Total / Total Penjualan / Total Pembayaran
- Biaya Layanan / MDR / Potongan (jika non-tunai)
- Net Settlement / Total Bersih
- Status Pesanan (Selesai, Lunas, Dibatalkan, dsb.)
"""

import re
from typing import Tuple, List, Union, Optional, Any
import pandas as pd

from core.models import SourceChannel, CanonicalTransaction
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe


class JubelioPosParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "POS_JUBELIO"

    @property
    def channel_name(self) -> str:
        return "Jubelio POS & Omnichannel Sales Report"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.POS_JUBELIO

    def classify_channel_type(self) -> str:
        return "POS"

    def get_matching_strategy(self) -> str:
        return "CROSS_VALIDATION"

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        """
        Deteksi apakah file adalah ekspor Jubelio POS / Omnichannel.
        """
        fn_lower = filename.lower()
        if "jubelio" in fn_lower:
            return True

        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            has_order_col = any(k in col_str for k in ["no. pesanan", "no pesanan", "nomor pesanan", "so number", "order no"])
            has_pos_indicators = any(k in col_str for k in ["metode pembayaran", "payment method", "lokasi", "toko", "cabang", "jubelio", "grand total"])
            if has_order_col and has_pos_indicators:
                return True

        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        """
        Membaca dan memetakan data transaksi Jubelio POS ke CanonicalTransaction.
        """
        df = load_dataframe(source, filename)
        txns: List[CanonicalTransaction] = []

        # Resolusi dinamis nama kolom Jubelio
        c_order = next((c for c in df.columns if any(k in c.lower() for k in ["no. pesanan", "no pesanan", "nomor pesanan", "so number", "order no", "no. transaksi", "no transaksi"])), df.columns[0])
        c_ref = next((c for c in df.columns if any(k in c.lower() for k in ["no. referensi", "no referensi", "nomor referensi", "ref no", "reference", "no. invoice", "invoice"])), None)
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["tanggal pesanan", "tanggal transaksi", "tanggal", "order date", "waktu", "created"])), df.columns[1] if len(df.columns) > 1 else df.columns[0])
        c_outlet = next((c for c in df.columns if any(k in c.lower() for k in ["toko", "lokasi", "cabang", "outlet", "store", "gudang"])), None)
        c_kasir = next((c for c in df.columns if any(k in c.lower() for k in ["kasir", "user", "sales", "operator"])), None)
        c_payment = next((c for c in df.columns if any(k in c.lower() for k in ["metode pembayaran", "payment method", "cara bayar", "tipe pembayaran", "payment"])), None)
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["grand total", "total penjualan", "total pesanan", "total pembayaran", "total", "jumlah bayar"])), df.columns[2] if len(df.columns) > 2 else df.columns[0])
        c_fee = next((c for c in df.columns if any(k in c.lower() for k in ["biaya layanan", "biaya mdr", "biaya pembayaran", "mdr", "fee", "komisi", "potongan fee"])), None)
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["total bersih", "net amount", "net settlement", "penerimaan bersih", "net"])), None)
        c_status = next((c for c in df.columns if any(k in c.lower() for k in ["status pesanan", "status transaksi", "status pembayaran", "status"])), None)

        for idx, r in df.iterrows():
            order_id = str(r.get(c_order, f"JBL-SO-{idx+1}")).strip()
            if not order_id or order_id.lower() == "nan":
                order_id = f"JBL-SO-{idx+1}"

            dt_raw = str(r.get(c_date, ""))
            dt = clean_date(dt_raw)

            outlet = str(r.get(c_outlet, "Outlet Utama")).strip() if c_outlet and not pd.isna(r.get(c_outlet)) else "Outlet Utama"
            kasir = str(r.get(c_kasir, "Kasir")).strip() if c_kasir and not pd.isna(r.get(c_kasir)) else "Kasir"
            payment_method = str(r.get(c_payment, "Tunai")).strip() if c_payment and not pd.isna(r.get(c_payment)) else "Tunai"
            
            ref_raw = r.get(c_ref) if c_ref else ""
            ref_no = str(ref_raw).strip() if ref_raw is not None and not pd.isna(ref_raw) and str(ref_raw).strip().lower() != "nan" else ""
            
            status_val = str(r.get(c_status, "SELESAI")).strip().upper() if c_status and not pd.isna(r.get(c_status)) else "SELESAI"

            gross = clean_number(r.get(c_gross, 0))
            if gross <= 0 and gross != 0:
                gross = abs(gross)

            # Kalkulasi MDR / Fee otomatis berdasarkan payment method jika tidak ada nilai fee eksplisit
            fee_raw = r.get(c_fee) if c_fee else None
            if fee_raw is not None and not pd.isna(fee_raw) and str(fee_raw).strip() != "":
                fee = clean_number(fee_raw)
            else:
                pm_upper = payment_method.upper()
                if "QRIS" in pm_upper:
                    fee = round(gross * 0.007, 2)  # Standar QRIS MDR 0.7%
                elif any(k in pm_upper for k in ["EDC", "KARTU KREDIT", "CREDIT CARD"]):
                    fee = round(gross * 0.015, 2)  # Standar EDC MDR 1.5%
                elif any(k in pm_upper for k in ["GOPAY", "OVO", "DANA", "SHOPEEPAY"]):
                    fee = round(gross * 0.012, 2)  # E-Wallet MDR 1.2%
                else:
                    fee = 0.0  # Tunai atau transfer langsung tanpa fee

            if c_net and not pd.isna(r.get(c_net)):
                net = clean_number(r.get(c_net, 0))
            else:
                net = round(gross - fee, 2)

            # Batch grouping berdasarkan tanggal dan outlet
            outlet_slug = re.sub(r"[^A-Za-z0-9]+", "-", outlet).strip("-").upper()
            batch_id = f"BATCH-JBL-{outlet_slug}-{dt[:10]}" if dt else f"BATCH-JBL-{outlet_slug}"

            desc_parts = [f"Jubelio POS #{order_id}"]
            if outlet:
                desc_parts.append(outlet)
            if payment_method:
                desc_parts.append(f"({payment_method})")
            if ref_no:
                desc_parts.append(f"Ref:{ref_no}")

            desc = " - ".join(desc_parts)

            txns.append(CanonicalTransaction(
                txn_id=order_id,
                source_channel=SourceChannel.POS_JUBELIO,
                date=dt,
                description=desc,
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=batch_id,
                raw_status=status_val,
                metadata={
                    "lokasi": outlet,
                    "kasir": kasir,
                    "metode_pembayaran": payment_method,
                    "no_referensi": ref_no,
                    "source": "Jubelio POS / Omnichannel"
                }
            ))

        return self.source_channel, txns
