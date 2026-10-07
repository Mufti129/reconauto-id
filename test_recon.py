"""
test_recon.py
-------------
Script verifikasi cepat untuk engine rekonsiliasi.
"""

import glob
from core.parser import parse_file
from core.engine import BidirectionalReconciliationEngine
from core.exporter import generate_reconciliation_excel, generate_journal_csv

def main():
    files = glob.glob("sample_data/*.csv")
    print(f"[TEST] Menemukan {len(files)} file di sample_data:")
    
    bank_rows = []
    source_txns = []
    cod_settlements = []

    for f in sorted(files):
        with open(f, "rb") as fp:
            channel, data = parse_file(fp.read(), filename=f)
            print(f"  - {f} => Channel: {channel.value} ({len(data)} baris)")
            if "BANK" in channel.value:
                bank_rows.extend(data)
            elif "LOGISTICS" in channel.value:
                cod_settlements.extend(data)
            else:
                source_txns.extend(data)

    engine = BidirectionalReconciliationEngine()
    result = engine.reconcile(bank_rows, source_txns, cod_settlements=cod_settlements)
    summary = result["summary"]

    print("\n[TEST] HASIL SUMMARY REKONSILIASI:")
    print(f"  - Total Penjualan Kotor (Gross)   : Rp {summary['total_gross_sales']:,.2f}")
    print(f"  - Total Potongan Fee Platform      : Rp {summary['total_platform_fees']:,.2f}")
    print(f"  - Total Penjualan Bersih (Expected): Rp {summary['total_expected_net']:,.2f}")
    print(f"  - Total Cair ke Bank (Cleared)     : Rp {summary['total_bank_cleared']:,.2f}")
    print(f"  - Dana In-Transit (Timing Lag)     : Rp {summary['in_transit_amount']:,.2f}")
    print(f"  - Dana Hilang (Missing Payout)     : Rp {summary['missing_payout_amount']:,.2f}")
    print(f"  - Kas Toko Belum Disetor           : Rp {summary['unsettled_cash_amount']:,.2f}")
    print(f"  - Selisih Kasir (Cash Shortage)    : Rp {summary['cash_shortage']:,.2f}")
    print(f"  - Setoran Bank Tak Dikenal         : Rp {summary['unidentified_bank_credits']:,.2f}")
    print(f"  - Bunga Bank                       : Rp {summary['bank_interest_income']:,.2f}")
    print(f"  - Biaya/Pajak Bank                 : Rp {summary['bank_charges']:,.2f}")
    print(f"  - Match Rate                       : {summary['match_rate_pct']}%")
    print(f"  - Bukti Selisih Kas (Proof Diff)   : Rp {summary['proof_difference']:,.2f}")
    print(f"  - Status Seimbang (Tied $0)?       : {summary['is_balanced']}")

    print(f"\n[TEST] Total Batch Payout: {len(result['batches'])}")
    print(f"[TEST] Total Discrepancy Terdeteksi: {len(result['discrepancies'])}")
    for d in result['discrepancies']:
        print(f"    * [{d['direction']}] [{d['severity']}] {d['issue_type']}: Rp {d['discrepancy_amount']:,.2f} ({d['probable_cause']})")

    excel_data = generate_reconciliation_excel(result)
    print(f"\n[TEST] Excel Report berhasil digenerate: {len(excel_data.getvalue())} bytes")
    
    journal_data = generate_journal_csv(result)
    print(f"[TEST] Jurnal CSV berhasil digenerate: {len(journal_data.splitlines())} baris")

if __name__ == "__main__":
    main()
