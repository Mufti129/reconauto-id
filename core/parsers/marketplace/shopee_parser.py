"""
core/parsers/marketplace/shopee_parser.py
Adapter untuk laporan settlement penghasilan Shopee Seller Centre (My Income).
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, CanonicalTransaction
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe

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
            has_shopee_specific = any(k in col_str for k in ["total penghasilan", "penarikan dana", "shopee", "no. penarikan dana"])
            return has_shopee_specific and ("pesanan" in col_str or "order" in col_str or "penghasilan" in col_str)
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []

        c_oid = next((c for c in df.columns if any(k in c.lower() for k in ["pesanan", "order"])), "No. Pesanan")
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["waktu", "tanggal", "date"])), "Waktu Pesanan Selesai")
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["total penghasilan", "net"])), "Total Penghasilan (Rp)")
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["harga asli", "gross"])), "Harga Asli Produk")
        c_adm = next((c for c in df.columns if "administrasi" in c.lower()), "Potongan Biaya Administrasi")
        c_layanan = next((c for c in df.columns if "layanan" in c.lower()), "Biaya Layanan")
        c_batch = next((c for c in df.columns if any(k in c.lower() for k in ["penarikan", "payout", "batch"])), "No. Penarikan Dana")

        for idx, r in df.iterrows():
            oid = str(r.get(c_oid, f"SHP-ROW-{idx+1}")).strip()
            batch = str(r.get(c_batch, "SHP-WD-UNKNOWN")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = clean_number(r.get(c_gross, 0))
            net = clean_number(r.get(c_net, 0))
            fee = clean_number(r.get(c_adm, 0)) + clean_number(r.get(c_layanan, 0))

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
                    "biaya_administrasi": clean_number(r.get(c_adm, 0)),
                    "biaya_layanan": clean_number(r.get(c_layanan, 0))
                }
            ))
        return SourceChannel.MARKETPLACE_SHOPEE, txns
