"""
core/parsers/pos/pos_cash_parser.py
Adapter untuk rekap setoran kasir fisik toko harian (Point of Sale - Kasir Tunai).
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, CanonicalTransaction
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe

class PosCashParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "POS_CASH"

    @property
    def channel_name(self) -> str:
        return "Kasir POS Tunai Toko Fisik"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.POS_CASH

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if "jubelio" in fn_lower:
            return False
        if "kasir_tunai" in fn_lower or "pos_tunai" in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            if any(k in col_str for k in ["no. pesanan", "no pesanan", "so number", "jubelio"]):
                return False
            return any(k in col_str for k in ["setor bank ref", "selisih kasir", "net setor", "shortage"]) or ("kasir" in col_str and "shift" in col_str)
        if "pos" in fn_lower or "kasir" in fn_lower:
            return True
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[CanonicalTransaction]]:
        df = load_dataframe(source, filename)
        txns = []

        c_id = next((c for c in df.columns if any(k in c.lower() for k in ["no transaksi", "no. struk", "invoice"])), "No Transaksi")
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["tanggal", "date", "waktu"])), "Tanggal")
        c_desc = next((c for c in df.columns if any(k in c.lower() for k in ["keterangan", "deskripsi", "item"])), "Keterangan")
        c_gross = next((c for c in df.columns if any(k in c.lower() for k in ["total kas", "total belanja", "gross"])), "Total Belanja (Gross)")
        c_short = next((c for c in df.columns if any(k in c.lower() for k in ["selisih", "shortage", "kurang"])), "Selisih Kasir (Shortage)")
        c_setor = next((c for c in df.columns if any(k in c.lower() for k in ["setor kas", "net setor", "net"])), "Net Setor Kas")
        c_batch = next((c for c in df.columns if any(k in c.lower() for k in ["setor bank ref", "batch ref", "ref setor"])), "Setor Bank Ref")
        c_kasir = next((c for c in df.columns if "kasir" in c.lower()), "Kasir")

        for idx, r in df.iterrows():
            pos_id = str(r.get(c_id, f"POS-{idx+1}")).strip()
            batch = str(r.get(c_batch, "POS-CASH-UNKNOWN")).strip()
            dt = clean_date(r.get(c_date, ""))
            desc = str(r.get(c_desc, f"Penjualan Kasir #{pos_id}")).strip()
            gross = clean_number(r.get(c_gross, 0))
            short = clean_number(r.get(c_short, 0))
            setor = clean_number(r.get(c_setor, 0)) or (gross - short)
            kasir_name = str(r.get(c_kasir, "Kasir-1")).strip()

            txns.append(CanonicalTransaction(
                txn_id=pos_id,
                source_channel=SourceChannel.POS_CASH,
                date=dt,
                description=f"{desc} (Kasir: {kasir_name})",
                gross_amount=gross,
                fee_amount=short,
                net_amount=setor,
                batch_id=batch,
                raw_status="SETOR_CDM" if batch != "BELUM_SETOR" else "CASH_IN_DRAWER",
                metadata={"kasir": kasir_name, "shortage": short}
            ))
        return SourceChannel.POS_CASH, txns
