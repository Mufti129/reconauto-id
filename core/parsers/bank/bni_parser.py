"""
core/parsers/bank/bni_parser.py
Adapter untuk mutasi rekening koran Bank BNI (BNI Direct / Corporate Internet Banking).
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, BankStatementRow
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe

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
        rows = []

        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["post date", "tanggal", "tgl", "txn date"])), df.columns[0])
        c_desc = next((c for c in df.columns if any(k in c.lower() for k in ["uraian", "keterangan", "description"])), df.columns[1])
        c_debit = next((c for c in df.columns if any(k in c.lower() for k in ["debet", "debit"])), None)
        c_kredit = next((c for c in df.columns if any(k in c.lower() for k in ["kredit", "credit"])), None)
        c_bal = next((c for c in df.columns if any(k in c.lower() for k in ["saldo", "balance"])), None)

        for idx, r in df.iterrows():
            desc = str(r.get(c_desc, "")).strip()
            date_str = clean_date(r.get(c_date, ""))
            bal = clean_number(r.get(c_bal)) if c_bal else None

            if c_debit and c_kredit:
                deb = clean_number(r.get(c_debit, 0))
                kred = clean_number(r.get(c_kredit, 0))
                if kred > 0:
                    amount, txn_type = kred, "CR"
                elif deb > 0:
                    amount, txn_type = deb, "DB"
                else:
                    continue
            else:
                c_amt = next((c for c in df.columns if any(k in c.lower() for k in ["nominal", "jumlah", "amount"])), df.columns[-1])
                amt_raw = clean_number(r.get(c_amt, 0))
                amount, txn_type = abs(amt_raw), ("CR" if amt_raw >= 0 else "DB")

            if "SALDO AWAL" in desc.upper():
                continue

            rows.append(BankStatementRow(
                row_id=f"BNI-ROW-{idx+1}",
                date=date_str,
                description=desc,
                amount=amount,
                txn_type=txn_type,
                bank_code="BANK_BNI",
                balance=bal,
                raw_data=r.to_dict()
            ))
        return SourceChannel.BANK_BNI, rows
