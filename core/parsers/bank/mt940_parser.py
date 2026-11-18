"""
core/parsers/bank/mt940_parser.py
Adapter untuk format standar industri perbankan internasional:
- SWIFT MT940 (.sta, .mt940, .swift, .mt9) termasuk narasi :86: multi-baris & indikator RC/RD
- Quicken Interchange Format (.qif) (!Type:Bank, D, T, P, M, N, ^)
- BAI2 Cash Management Format (.bai, .bai2) (Record 16 & 88)
"""

import os
import re
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
        return "Standard Banking SWIFT MT940 / BAI2 / QIF"

    @property
    def source_channel(self) -> SourceChannel:
        return SourceChannel.BANK_SWIFT_MT940

    def detect_format(self, df: Optional[pd.DataFrame] = None, filename: str = "", raw_text: str = "") -> bool:
        fn_lower = filename.lower()
        if fn_lower.endswith((".sta", ".mt940", ".swift", ".mt9", ".qif", ".bai", ".bai2")):
            return True
        if raw_text:
            rt_up = raw_text.upper()
            if (":20:" in rt_up and ":61:" in rt_up) or rt_up.lstrip().startswith("!TYPE:") or rt_up.lstrip().startswith("01,"):
                return True
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        if isinstance(source, bytes):
            text = source.decode("utf-8-sig", errors="ignore")
        elif hasattr(source, "read"):
            if hasattr(source, "seek"):
                source.seek(0)
            content = source.read()
            text = content.decode("utf-8-sig", errors="ignore") if isinstance(content, bytes) else str(content)
        elif isinstance(source, str) and os.path.exists(source):
            with open(source, "r", encoding="utf-8-sig", errors="ignore") as f:
                text = f.read()
        else:
            text = str(source)

        fn_lower = filename.lower()
        text_strip = text.lstrip()

        # 1. Cek apakah format QIF (Quicken Interchange Format: !Type:Bank)
        if fn_lower.endswith(".qif") or text_strip.upper().startswith("!TYPE:"):
            return self.source_channel, self._parse_qif(text)

        # 2. Cek apakah format BAI2 Treasury Cash Management (01, ... 16, ...)
        if fn_lower.endswith((".bai", ".bai2")) or text_strip.startswith("01,"):
            return self.source_channel, self._parse_bai2(text)

        # 3. Default: SWIFT MT940 (:20:, :61:, :86: multi-line)
        rows: List[BankStatementRow] = []
        lines = text.splitlines()
        current_row: Optional[BankStatementRow] = None
        in_tag_86 = False
        idx = 0

        # Pattern :61: YYMMDD[MMDD](C|D|RC|RD|EC|ED)[A-Z]?(Amount)N[A-Z0-9]{3}(Reference)
        line_61_regex = re.compile(r"^:61:(\d{6})(?:\d{4})?(RC|RD|EC|ED|CR|DR|C|D)([A-Z])?([0-9,\.]+)(?:N[A-Z0-9]{3}([^\r\n]*))?")

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith(":61:"):
                in_tag_86 = False
                m = line_61_regex.search(line_str)
                if m:
                    yymmdd, cd, _, amt_str, inline_ref = m.groups()
                    iso_date = f"20{yymmdd[0:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}"
                    amt = abs(clean_number(amt_str))
                    cd_up = cd.upper()
                    # RC = Reversal Credit (artinya didebit balik), RD = Reversal Debit (dikredit balik)
                    if cd_up in ("C", "CR", "EC", "RD"):
                        txn_type = "CR"
                    else:
                        txn_type = "DB"
                    idx += 1
                    ref_clean = (inline_ref or "").replace("//", " ").strip()
                    current_row = BankStatementRow(
                        row_id=f"MT940-{idx}",
                        date=iso_date,
                        description=ref_clean if ref_clean else f"MT940 Transaction #{idx}",
                        amount=amt,
                        txn_type=txn_type,
                        bank_code="BANK_SWIFT_MT940"
                    )
                    rows.append(current_row)
            elif line_str.startswith(":86:") and current_row:
                in_tag_86 = True
                desc = line_str[4:].strip()
                if desc:
                    if current_row.description.startswith("MT940 Transaction"):
                        current_row.description = desc
                    elif desc not in current_row.description:
                        current_row.description = f"{current_row.description} {desc}".strip()
            elif line_str.startswith(":"):
                in_tag_86 = False
            elif in_tag_86 and current_row and not line_str.startswith("-"):
                current_row.description = f"{current_row.description} {line_str}".strip()

        return SourceChannel.BANK_SWIFT_MT940, rows

    def _parse_qif(self, text: str) -> List[BankStatementRow]:
        """Mem-parsing format Quicken Interchange Format (.qif)."""
        rows: List[BankStatementRow] = []
        blocks = text.split("^")
        for idx, blk in enumerate(blocks, 1):
            dt_str = "2026-08-15"
            amt_val = 0.0
            payee = ""
            memo = ""
            ref = ""
            for raw_ln in blk.splitlines():
                ln = raw_ln.strip()
                if not ln or ln.startswith("!"):
                    continue
                code, val = ln[0].upper(), ln[1:].strip()
                if code == "D":
                    dt_str = clean_date(val)
                elif code == "T":
                    amt_val = clean_number(val)
                elif code == "P":
                    payee = val
                elif code == "M":
                    memo = val
                elif code == "N":
                    ref = val
            if abs(amt_val) > 0:
                desc = " - ".join(p for p in (payee, memo, ref) if p) or f"QIF Entry #{idx}"
                rows.append(BankStatementRow(
                    row_id=f"QIF-{idx}",
                    date=dt_str or "2026-08-15",
                    description=desc,
                    amount=abs(amt_val),
                    txn_type="CR" if amt_val >= 0 else "DB",
                    bank_code="BANK_SWIFT_MT940"
                ))
        return rows

    def _parse_bai2(self, text: str) -> List[BankStatementRow]:
        """Mem-parsing format standar treasury BAI2 (Record 16 detail & Record 88 continuation)."""
        rows: List[BankStatementRow] = []
        current_row: Optional[BankStatementRow] = None
        current_date = "2026-08-15"
        idx = 0

        for raw_ln in text.splitlines():
            ln = raw_ln.strip().rstrip("/")
            if not ln:
                continue
            parts = [p.strip() for p in ln.split(",")]
            rec_code = parts[0]
            if rec_code == "02" and len(parts) >= 5:
                # Group Header berisi tanggal YYMMDD pada indeks 4
                yymmdd = parts[4]
                if len(yymmdd) == 6 and yymmdd.isdigit():
                    current_date = f"20{yymmdd[:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}"
            elif rec_code == "16" and len(parts) >= 3:
                idx += 1
                type_code = int(parts[1]) if parts[1].isdigit() else 100
                amt = abs(clean_number(parts[2]))
                # Di BAI2, type code 100-399 adalah Credit, 400-699 adalah Debit
                txn_type = "DB" if 400 <= type_code < 700 else "CR"
                desc = " ".join(parts[3:]).strip() or f"BAI2 Txn #{idx}"
                current_row = BankStatementRow(
                    row_id=f"BAI2-{idx}",
                    date=current_date,
                    description=desc,
                    amount=amt,
                    txn_type=txn_type,
                    bank_code="BANK_SWIFT_MT940"
                )
                rows.append(current_row)
            elif rec_code == "88" and current_row and len(parts) >= 2:
                cont_text = " ".join(parts[1:]).strip()
                if cont_text:
                    current_row.description = f"{current_row.description} {cont_text}".strip()
        return rows
