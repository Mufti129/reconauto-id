"""
core/parsers/marketplace/shopee_parser.py
Adapter untuk laporan settlement penghasilan Shopee Seller Centre (My Income / Penghasilan Saya).
Mendukung ekspor Bahasa Indonesia & Bahasa Inggris, serta normalisasi tanda negatif pada potongan biaya.
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, CanonicalTransaction
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe, is_summary_or_noise_row


class ShopeeParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "MARKETPLACE_SHOPEE"

    @property
    def channel_name(self) -> str:
        return "Shopee Seller Centre (Penghasilan Saya)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.MARKETPLACE_SHOPEE

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if "shopee" in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            has_shopee_specific = any(k in col_str for k in [
                "total penghasilan", "penarikan dana", "shopee", "no. penarikan dana",
                "total released amount", "escrow release", "shopee voucher"
            ])
            return has_shopee_specific and any(k in col_str for k in ["pesanan", "order", "penghasilan", "released"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []
        if df is None or df.empty:
            return SourceChannel.MARKETPLACE_SHOPEE, txns

        c_oid = next((c for c in df.columns if any(k in c.lower() for k in ["no. pesanan", "no pesanan", "order id", "order_id", "pesanan", "order"])), df.columns[0])
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["waktu pesanan", "payout completed", "order complete", "waktu", "tanggal", "date"])), df.columns[1] if len(df.columns) > 1 else df.columns[0])
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["total penghasilan", "total released", "escrow amount", "net amount", "net"])), None)
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["harga asli", "original price", "product price", "total harga", "gross"])), None)
        c_adm = next((c for c in df.columns if any(k in c.lower() for k in ["administrasi", "admin fee", "commission fee", "komisi"])), None)
        c_layanan = next((c for c in df.columns if any(k in c.lower() for k in ["layanan", "service fee", "transaction fee"])), None)
        c_batch = next((c for c in df.columns if any(k in c.lower() for k in ["penarikan", "payout", "batch", "withdrawal"])), None)

        for idx, r in df.iterrows():
            oid = str(r.get(c_oid, f"SHP-ROW-{idx+1}")).strip()
            if not oid or is_summary_or_noise_row(oid):
                continue
            dt = clean_date(r.get(c_date, "")) or "2026-08-15"
            batch = str(r.get(c_batch, f"SHP-WD-{dt[:10]}")).strip() if (c_batch and not pd.isna(r.get(c_batch))) else f"SHP-WD-{dt[:10]}"

            gross = abs(clean_number(r.get(c_gross, 0))) if c_gross else 0.0
            net = clean_number(r.get(c_net, 0)) if c_net else 0.0
            adm_f = abs(clean_number(r.get(c_adm, 0))) if c_adm else 0.0
            lay_f = abs(clean_number(r.get(c_layanan, 0))) if c_layanan else 0.0
            fee = adm_f + lay_f

            if gross == 0.0 and net > 0.0:
                gross = net + fee
            elif net == 0.0 and gross > 0.0:
                net = gross - fee

            if gross <= 0 and net <= 0:
                continue

            txns.append(CanonicalTransaction(
                txn_id=oid,
                source_channel=SourceChannel.MARKETPLACE_SHOPEE,
                date=dt,
                description=f"Shopee Order {oid}",
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=batch,
                raw_status=str(r.get("Status", "Selesai")),
                metadata={
                    "biaya_administrasi": adm_f,
                    "biaya_layanan": lay_f
                }
            ))
        return SourceChannel.MARKETPLACE_SHOPEE, txns
