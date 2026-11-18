"""
core/parsers/marketplace/tiktok_parser.py
Adapter untuk laporan settlement pesanan TikTok Shop Seller Center.
Mendukung ekspor Bahasa Inggris & Bahasa Indonesia, serta normalisasi tanda negatif pada kolom potongan komisi.
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, CanonicalTransaction
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe, is_summary_or_noise_row


class TiktokShopParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "MARKETPLACE_TIKTOK"

    @property
    def channel_name(self) -> str:
        return "TikTok Shop Seller Center"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.MARKETPLACE_TIKTOK

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if "tiktok" in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            return any(k in col_str for k in [
                "statement id", "referral fee", "total settlement amount", "sku id",
                "id laporan", "biaya referral", "total jumlah penyelesaian"
            ])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []
        if df is None or df.empty:
            return SourceChannel.MARKETPLACE_TIKTOK, txns

        c_oid = next((c for c in df.columns if any(k in c.lower() for k in ["order id", "order/adjustment", "id pesanan", "no pesanan", "order_id"])), df.columns[0])
        c_stmt = next((c for c in df.columns if any(k in c.lower() for k in ["statement id", "id laporan", "settlement id", "batch id"])), None)
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["statement date", "tanggal laporan", "order settled time", "date", "tanggal", "waktu"])), df.columns[1] if len(df.columns) > 1 else df.columns[0])
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["gross sales", "penjualan kotor", "subtotal before", "harga asli", "gross"])), None)
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["settlement amount", "jumlah penyelesaian", "total net", "net amount", "penghasilan bersih", "net"])), None)
        c_ref_fee = next((c for c in df.columns if any(k in c.lower() for k in ["referral fee", "biaya referral", "platform commission", "komisi"])), None)
        c_tx_fee = next((c for c in df.columns if any(k in c.lower() for k in ["transaction fee", "biaya transaksi", "payment fee"])), None)
        c_ship = next((c for c in df.columns if any(k in c.lower() for k in ["shipping fee", "biaya pengiriman", "selisih ongkir"])), None)
        c_total_fee = next((c for c in df.columns if any(k in c.lower() for k in ["total fees", "total biaya", "fee_amount", "fee"]) and c not in (c_ref_fee, c_tx_fee, c_ship)), None)
        c_sku = next((c for c in df.columns if "sku" in c.lower()), None)

        for idx, r in df.iterrows():
            oid = str(r.get(c_oid, f"TT-ROW-{idx+1}")).strip()
            if not oid or is_summary_or_noise_row(oid):
                continue
            dt = clean_date(r.get(c_date, "")) or "2026-08-15"
            stmt = str(r.get(c_stmt, f"TT-BATCH-{dt[:10]}")).strip() if (c_stmt and not pd.isna(r.get(c_stmt))) else f"TT-BATCH-{dt[:10]}"

            gross = abs(clean_number(r.get(c_gross, 0))) if c_gross else 0.0
            net = clean_number(r.get(c_net, 0)) if c_net else 0.0

            ref_f = abs(clean_number(r.get(c_ref_fee, 0))) if c_ref_fee else 0.0
            tx_f = abs(clean_number(r.get(c_tx_fee, 0))) if c_tx_fee else 0.0
            ship_f = abs(clean_number(r.get(c_ship, 0))) if c_ship else 0.0
            tot_f = abs(clean_number(r.get(c_total_fee, 0))) if c_total_fee else 0.0

            fee = (ref_f + tx_f + ship_f) if (ref_f + tx_f + ship_f) > 0 else tot_f
            if gross == 0.0 and net > 0.0:
                gross = net + fee
            elif net == 0.0 and gross > 0.0:
                net = gross - fee

            if gross <= 0 and net <= 0:
                continue

            txns.append(CanonicalTransaction(
                txn_id=oid,
                source_channel=SourceChannel.MARKETPLACE_TIKTOK,
                date=dt,
                description=f"TikTok Order {oid}",
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=stmt,
                raw_status=str(r.get("Status", "Completed")),
                metadata={
                    "referral_fee": ref_f,
                    "transaction_fee": tx_f,
                    "sku": str(r.get(c_sku, "")) if c_sku else ""
                }
            ))
        return SourceChannel.MARKETPLACE_TIKTOK, txns
