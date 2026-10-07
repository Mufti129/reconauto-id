"""
core/parsers/bank/mandiri_parser.py
Adapter untuk mutasi rekening koran Bank Mandiri (Kopra by Mandiri / MCM / Corporate).
"""

from typing import Tuple, List, Union, Optional, Any
import pandas as pd
from core.models import SourceChannel, BankStatementRow
from core.parsers.base import BaseChannelParser, clean_number, clean_date, load_dataframe

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
            # Mandiri khas: ada kolom debit dan kredit terpisah, atau referensi mandiri / teller
            has_mandiri_keywords = any(k in col_str for k in ["mandiri", "debit", "kredit", "no. referensi", "remark", "posting date", "value date"])
            has_db_cr_split = ("debit" in col_str and "kredit" in col_str) or ("debet" in col_str and "kredit" in col_str)
            return (has_mandiri_keywords and has_db_cr_split) or ("mandiri" in col_str)
        return False

    def parse(self, source: Union[str, Any], filename: str = "") -> Tuple[SourceChannel, List[BankStatementRow]]:
        df = load_dataframe(source, filename)
        rows = []

        cols = [c.lower() for c in df.columns]
        c_date = next((c for c in df.columns if any(k in c.lower() for k in ["post date", "posting date", "tanggal", "tgl", "date"])), df.columns[0])
        c_desc = next((c for c in df.columns if any(k in c.lower() for k in ["keterangan", "remark", "description", "uraian"])), df.columns[1])
        c_ref = next((c for c in df.columns if any(k in c.lower() for k in ["referensi", "ref no", "reference"])), None)
        c_debit = next((c for c in df.columns if any(k in c.lower() for k in ["debit", "debet"])), None)
        c_kredit = next((c for c in df.columns if any(k in c.lower() for k in ["kredit", "credit"])), None)
        c_bal = next((c for c in df.columns if any(k in c.lower() for k in ["saldo", "balance"])), None)

        for idx, r in df.iterrows():
            desc = str(r.get(c_desc, "")).strip()
            date_str = clean_date(r.get(c_date, ""))
            ref_no = str(r.get(c_ref, "")).strip() if c_ref else ""
            if ref_no and ref_no not in desc:
                desc = f"{desc} [Ref: {ref_no}]".strip()

            bal = clean_number(r.get(c_bal)) if c_bal else None
            
            # Format 2 Kolom: Debit & Kredit terpisah
            if c_debit and c_kredit:
                deb_val = clean_number(r.get(c_debit, 0))
                kred_val = clean_number(r.get(c_kredit, 0))
                if kred_val > 0:
                    amount = kred_val
                    txn_type = "CR"
                elif deb_val > 0:
                    amount = deb_val
                    txn_type = "DB"
                else:
                    continue
            else:
                # Kolom jumlah tunggal
                c_amt = next((c for c in df.columns if any(k in c.lower() for k in ["jumlah", "amount", "mutasi"])), df.columns[-1])
                amt_raw = clean_number(r.get(c_amt, 0))
                txn_type = "CR" if amt_raw >= 0 else "DB"
                amount = abs(amt_raw)

            if "SALDO AWAL" in desc.upper():
                continue

            rows.append(BankStatementRow(
                row_id=f"MANDIRI-ROW-{idx+1}",
                date=date_str,
                description=desc,
                amount=amount,
                txn_type=txn_type,
                bank_code="BANK_MANDIRI",
                balance=bal,
                raw_data=r.to_dict()
            ))
        return SourceChannel.BANK_MANDIRI, rows
