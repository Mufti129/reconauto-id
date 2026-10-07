"""
core/parsers/logistics/sicepat_cod_parser.py
Adapter untuk laporan settlement pencairan Cash on Delivery (COD) SiCepat Express.
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, CodSettlementRow
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe

class SicepatCodParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "LOGISTICS_SICEPAT_COD"

    @property
    def channel_name(self) -> str:
        return "SiCepat Express COD Settlement"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.LOGISTICS_SICEPAT_COD

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if "jne" in fn_lower:
            return False
        if "sicepat" in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            if "jne" in col_str:
                return False
            return ("sicepat" in col_str) or ("biaya layanan cod" in col_str) or ("net pencairan" in col_str)
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CodSettlementRow]]:
        df = load_dataframe(source, filename)
        rows = []

        c_awb = next((c for c in df.columns if any(k in c.lower() for k in ["no resi", "awb", "nomor resi"])), "No Resi")
        c_oid = next((c for c in df.columns if any(k in c.lower() for k in ["order id", "no pesanan", "kode order"])), "Order ID")
        c_cod = next((c for c in df.columns if any(k in c.lower() for k in ["nilai barang", "nilai cod", "total tagihan"])), "Nilai COD")
        c_fee = next((c for c in df.columns if any(k in c.lower() for k in ["biaya cod", "fee", "ongkir"])), "Biaya Layanan COD")
        c_net = next((c for c in df.columns if any(k in c.lower() for k in ["dana dicairkan", "total transfer", "net"])), "Net Pencairan")
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["tgl transfer", "tanggal", "settlement date"])), "Tgl Transfer")
        c_bank = next((c for c in df.columns if any(k in c.lower() for k in ["ref bank", "kode transfer", "nomor referensi"])), None)

        c_status = next((c for c in df.columns if any(k in c.lower() for k in ["status pod", "status delivery", "status"])), None)

        for idx, r in df.iterrows():
            awb = str(r.get(c_awb, f"004291{idx+1}")).strip()
            oid = str(r.get(c_oid, f"ORD-SCP-{idx+1}")).strip()
            cod_val = clean_number(r.get(c_cod, 0))
            fee_val = clean_number(r.get(c_fee, 0))
            net_val = clean_number(r.get(c_net, 0)) or (cod_val - fee_val)
            dt = clean_date(r.get(c_date, ""))
            b_ref_val = r.get(c_bank) if c_bank else None
            b_ref = None if (b_ref_val is None or pd.isna(b_ref_val) or str(b_ref_val).strip().lower() in ["", "nan", "none"]) else str(b_ref_val).strip()
            st = str(r.get(c_status, "DELIVERED")).strip().upper() if c_status else "DELIVERED"

            expected_net = cod_val - fee_val
            if not b_ref or "PENDING" in st or "UNREMIT" in st:
                status = "COD_UNREMITTED"
            elif (expected_net - net_val) > 1.0:
                status = "COD_SHORTAGE"
            else:
                status = "CLEARED"

            rows.append(CodSettlementRow(
                awb_number=awb,
                courier_name="SiCepat Express",
                order_id=oid,
                cod_amount=cod_val,
                courier_fee=fee_val,
                net_remitted=net_val,
                settlement_date=dt,
                bank_ref_id=b_ref,
                status=status,
                metadata={"courier": "SiCepat", "status_pod": st, "expected_net": expected_net}
            ))
        return SourceChannel.LOGISTICS_SICEPAT_COD, rows
