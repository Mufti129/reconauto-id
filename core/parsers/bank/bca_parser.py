"""
core/parsers/bank/bca_parser.py
Adapter untuk mutasi rekening koran Bank BCA (CSV, Excel, HTML .xls, JSON, & PDF KlikBCA / MCM).
Mendukung baik kolom tunggal (Jumlah + Tipe / embedded CR/DB) maupun kolom Debit & Kredit terpisah.
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, BankStatementRow
from core.parsers.base import BaseChannelParser, load_dataframe, extract_universal_bank_rows


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
        if any(other in fn_lower for other in ["bni", "bri", "mandiri", "kopra", "cimb", "permata", "bsi"]):
            return False
        if fn_lower.endswith(".pdf"):
            return "bca" in fn_lower or "rekening" in fn_lower or "statement" in fn_lower or "mutasi" in fn_lower
        if "bca" in fn_lower or "klikbca" in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            if any(other in col_str for other in ["bni", "bri", "mandiri", "kopra", "cimb", "permata", "bsi"]):
                return False
            return any(k in col_str for k in ["keterangan", "bcaamount", "saldo"]) and any(k in col_str for k in ["tipe", "jumlah", "db/cr", "mutasi"])
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        fn_lower = filename.lower()
        if fn_lower.endswith(".pdf"):
            from core.pdf_parser import parse_bank_pdf
            bank_rows = parse_bank_pdf(source)
            detected_code = "BANK_BCA"
            for code_kw, code_val in (("mandiri", "BANK_MANDIRI"), ("bni", "BANK_BNI"), ("bri", "BANK_BRI"), ("bsi", "BANK_BSI"), ("cimb", "BANK_CIMB")):
                if code_kw in fn_lower:
                    detected_code = code_val
                    break
            for b in bank_rows:
                b.bank_code = detected_code
            return SourceChannel.BANK_BCA, bank_rows

        df = load_dataframe(source, filename)
        rows = extract_universal_bank_rows(df, bank_code="BANK_BCA", row_prefix="BCA-ROW")
        return SourceChannel.BANK_BCA, rows
