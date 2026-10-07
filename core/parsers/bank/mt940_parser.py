"""
core/parsers/bank/mt940_parser.py
Adapter untuk format standar industri SWIFT MT940 / CAMT.053.
"""

import re
import io
from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, BankStatementRow
from core.parsers.base import BaseChannelParser, clean_number, clean_date

class Mt940Parser(BaseChannelParser):
    @property
    def channel_id(self) -> str:
        return "BANK_MT940"

    @property
    def channel_name(self) -> str:
        return "Standard Banking SWIFT MT940 / CAMT.053"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_SWIFT_MT940

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if fn_lower.endswith(".sta") or fn_lower.endswith(".mt940") or fn_lower.endswith(".swift"):
            return True
        if raw_text:
            return ":20:" in raw_text and ":61:" in raw_text
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        if isinstance(source, bytes):
            text = source.decode("utf-8", errors="ignore")
        elif hasattr(source, "read"):
            content = source.read()
            text = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)
        elif isinstance(source, str) and os.path.exists(source):
            with open(source, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        else:
            text = str(source)

        rows = []
        lines = text.splitlines()
        current_row: Optional[BankStatementRow] = None
        idx = 0

        # Pattern for :61: YYMMDD(M[M]D[D])(C|D|RC|RD)[A-Z](Amount)N(TransactionType)(Reference)
        # e.g., :61:2608150815CR850000,00NTRF//BCA-SETTLE-001
        line_61_regex = re.compile(r"^:61:(\d{6})(?:\d{4})?([A-Z]{1,2})([A-Z])?([0-9,\.]+)")

        for line in lines:
            line_str = line.strip()
            if line_str.startswith(":61:"):
                m = line_61_regex.search(line_str)
                if m:
                    yymmdd, cd, _, amt_str = m.groups()
                    iso_date = f"20{yymmdd[0:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}"
                    amt = clean_number(amt_str)
                    txn_type = "CR" if "C" in cd.upper() else "DB"
                    idx += 1
                    current_row = BankStatementRow(
                        row_id=f"MT940-{idx}",
                        date=iso_date,
                        description="MT940 Transaction",
                        amount=amt,
                        txn_type=txn_type,
                        bank_code="BANK_SWIFT_MT940"
                    )
                    rows.append(current_row)
            elif line_str.startswith(":86:") and current_row:
                desc = line_str[4:].strip()
                current_row.description = desc

        return SourceChannel.BANK_SWIFT_MT940, rows
