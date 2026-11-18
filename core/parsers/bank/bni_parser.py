"""
core/parsers/bank/bni_parser.py
Adapter untuk mutasi rekening koran Bank BNI (BNI Direct / Corporate Internet Banking).
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, BankStatementRow
from core.parsers.base import BaseChannelParser, load_dataframe, extract_universal_bank_rows


class BniParser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "BANK_BNI"

    @property
    def channel_name(self) -> str:
        return "Bank BNI (BNI Direct)"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_BNI

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if "bni" in fn_lower:
            return True
        if df is not None:
            col_str = " ".join([str(c).lower().strip() for c in df.columns])
            return ("bni" in col_str) or ("no. referensi bni" in col_str)
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        df = load_dataframe(source, filename)
        rows = extract_universal_bank_rows(df, bank_code="BANK_BNI", row_prefix="BNI-ROW")
        return SourceChannel.BANK_BNI, rows
