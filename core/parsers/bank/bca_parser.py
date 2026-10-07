"""
core/parsers/bank/bca_parser.py
Adapter untuk mutasi rekening koran Bank BCA (CSV & PDF KlikBCA / MCM).
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, BankStatementRow
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe

class BcaParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "BANK_BCA"

    @property
    def channel_name(self) -> str:
        return "Bank BCA (KlikBCA Bisnis / MCM / e-Statement)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_BCA

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if any(other in fn_lower for other in ["bni", "bri", "mandiri", "kopra"]):
            return False
        if fn_lower.endswith(".pdf"):
            return "bca" in fn_lower or "rekening" in fn_lower or "statement" in fn_lower
        if "bca" in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            if any(other in col_str for other in ["bni", "bri", "mandiri", "kopra"]):
                return False
            return any(k in col_str for k in ["keterangan", "bcaamount", "saldo"]) and any(k in col_str for k in ["tipe", "jumlah", "db/cr"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        if filename.lower().endswith(".pdf"):
            from core.pdf_parser import parse_bank_pdf
            bank_rows = parse_bank_pdf(source)
            for b in bank_rows:
                b.bank_code = "BANK_BCA"
            return SourceChannel.BANK_BCA, bank_rows

        df = load_dataframe(source, filename)
        rows = []
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["tgl", "tanggal", "date"])), df.columns[0])
        c_desc = next((c for c in df.columns if any(k in c.lower() for k in ["ket", "desc", "keterangan"])), df.columns[1])
        c_amt = next((c for c in df.columns if any(k in c.lower() for k in ["jum", "amount", "mutasi"])), df.columns[3] if len(df.columns) > 3 else df.columns[-1])
        c_type = next((c for c in df.columns if any(k in c.lower() for k in ["tipe", "type", "db/cr"])), None)
        c_bal = next((c for c in df.columns if any(k in c.lower() for k in ["saldo", "balance"])), None)

        for idx, r in df.iterrows():
            desc = str(r.get(c_desc, "")).strip()
            amt_raw = clean_number(r.get(c_amt, 0))
            date_str = clean_date(r.get(c_date, ""))

            txn_type = "CR"
            if c_type and str(r.get(c_type, "")).strip().upper() in ["DB", "DEBIT", "D"]:
                txn_type = "DB"
            elif amt_raw < 0:
                txn_type = "DB"
                amt_raw = abs(amt_raw)

            bal = clean_number(r.get(c_bal)) if c_bal else None
            if "SALDO AWAL" in desc.upper():
                continue

            rows.append(BankStatementRow(
                row_id=f"BCA-ROW-{idx+1}",
                date=date_str,
                description=desc,
                amount=amt_raw,
                txn_type=txn_type,
                bank_code="BANK_BCA",
                balance=bal,
                raw_data=r.to_dict()
            ))
        return SourceChannel.BANK_BCA, rows
