"""
core/parsers/marketplace/tiktok_parser.py
Adapter untuk laporan settlement pesanan TikTok Shop Seller Center.
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, CanonicalTransaction
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe

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
            return any(k in col_str for k in ["statement id", "referral fee", "total settlement amount", "sku id"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []

        c_oid = next((c for c in df.columns if any(k in c.lower() for k in ["order id", "order/adjustment"])), "Order ID")
        c_stmt = next((c for c in df.columns if "statement id" in c.lower()), "Statement ID")
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["statement date", "date", "tanggal"])), "Statement Date")
        c_gross = next((c for c in df.columns if "gross sales" in c.lower()), "Gross sales")
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["settlement amount", "total net", "net amount"])), "Total settlement amount")
        c_ref_fee = next((c for c in df.columns if "referral fee" in c.lower()), "Referral fee")
        c_tx_fee = next((c for c in df.columns if "transaction fee" in c.lower()), "Transaction fee")
        c_ship = next((c for c in df.columns if "shipping" in c.lower()), "Shipping fee")

        for idx, r in df.iterrows():
            oid = str(r.get(c_oid, f"TT-ROW-{idx+1}")).strip()
            stmt = str(r.get(c_stmt, "TT-BATCH-UNKNOWN")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = clean_number(r.get(c_gross, 0))
            net = clean_number(r.get(c_net, 0))
            fee = clean_number(r.get(c_ref_fee, 0)) + clean_number(r.get(c_tx_fee, 0)) + clean_number(r.get(c_ship, 0))

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
                    "referral_fee": clean_number(r.get(c_ref_fee, 0)),
                    "transaction_fee": clean_number(r.get(c_tx_fee, 0)),
                    "sku": str(r.get("SKU ID", ""))
                }
            ))
        return SourceChannel.MARKETPLACE_TIKTOK, txns
