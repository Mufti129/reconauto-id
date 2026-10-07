"""
core/parsers/payment_gateway/doku_parser.py
Adapter untuk laporan mutasi settlement DOKU Payment Gateway.
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, CanonicalTransaction
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe

class DokuParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "PAYMENT_GATEWAY_DOKU"

    @property
    def channel_name(self) -> str:
        return "DOKU Payment Gateway Settlement"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.PAYMENT_GATEWAY_DOKU

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if "doku" in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            return any(k in col_str for k in ["invoice id", "mdr fee", "settlement batch ref", "payment channel"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []

        c_inv = next((c for c in df.columns if any(k in c.lower() for k in ["invoice", "transaction id", "order id"])), "Invoice ID")
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["date", "tanggal", "waktu"])), "Payment Date")
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["gross", "amount", "total bayar"])), "Transaction Amount")
        c_fee = next((c for c in df.columns if any(k in c.lower() for k in ["mdr", "fee", "biaya"])), "MDR Fee")
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["net", "settlement"])), "Net Settlement")
        c_batch = next((c for c in df.columns if any(k in c.lower() for k in ["batch", "batch ref", "payout"])), "Settlement Batch Ref")
        c_chn = next((c for c in df.columns if any(k in c.lower() for k in ["channel", "metode"])), "Payment Channel")

        for idx, r in df.iterrows():
            inv = str(r.get(c_inv, f"DOKU-{idx+1}")).strip()
            batch = str(r.get(c_batch, "DOKU-BATCH-UNKNOWN")).strip()
            dt = clean_date(r.get(c_date, ""))
            gross = clean_number(r.get(c_gross, 0))
            fee = clean_number(r.get(c_fee, 0))
            net = clean_number(r.get(c_net, 0)) or (gross - fee)
            channel_name = str(r.get(c_chn, "QRIS/VA")).strip()

            txns.append(CanonicalTransaction(
                txn_id=inv,
                source_channel=SourceChannel.PAYMENT_GATEWAY_DOKU,
                date=dt,
                description=f"DOKU {channel_name} #{inv}",
                gross_amount=gross,
                fee_amount=fee,
                net_amount=net,
                batch_id=batch,
                raw_status="SUCCESS",
                metadata={"payment_channel": channel_name}
            ))
        return SourceChannel.PAYMENT_GATEWAY_DOKU, txns
