"""
core/parsers/bank/bri_parser.py
Adapter untuk mutasi rekening koran Bank BRI (CMS BRI / Cash Management).
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, BankStatementRow
from core.parsers.base import BaseChannelParser, load_dataframe, extract_universal_bank_rows


class BriParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "BANK_BRI"

    @property
    def channel_name(self) -> str:
        return "Bank BRI (CMS BRI)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_BRI

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if "bri" in fn_lower and "bni" not in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            return ("bri" in col_str) or ("transaksi bri" in col_str)
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        df = load_dataframe(source, filename)
        rows = extract_universal_bank_rows(df, bank_code="BANK_BRI", row_prefix="BRI-ROW")
        return SourceChannel.BANK_BRI, rows
