"""
core/parsers/bank/mandiri_parser.py
Adapter untuk mutasi rekening koran Bank Mandiri (Kopra by Mandiri / MCM / Corporate).
Mendukung kolom Debit & Kredit terpisah maupun kolom Jumlah tunggal di semua format berkas.
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, BankStatementRow
from core.parsers.base import BaseChannelParser, load_dataframe, extract_universal_bank_rows


class MandiriParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "BANK_MANDIRI"

    @property
    def channel_name(self) -> str:
        return "Bank Mandiri (Kopra by Mandiri / MCM)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_MANDIRI

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if "mandiri" in fn_lower or "kopra" in fn_lower or "mcm" in fn_lower:
            return True
        if df is not None:
            cols = [str(c).lower().strip() for c in df.columns]
            col_str = " ".join(cols)
            has_mandiri_keywords = any(k in col_str for k in ["mandiri", "no. referensi", "remark", "posting date", "value date"])
            has_db_cr_split = ("debit" in col_str and "kredit" in col_str) or ("debet" in col_str and "kredit" in col_str) or ("debit" in col_str and "credit" in col_str)
            return (has_mandiri_keywords and has_db_cr_split) or ("mandiri" in col_str)
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        df = load_dataframe(source, filename)
        rows = extract_universal_bank_rows(df, bank_code="BANK_MANDIRI", row_prefix="MANDIRI-ROW")
        return SourceChannel.BANK_MANDIRI, rows
