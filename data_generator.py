"""
data_generator.py
-----------------
Menghasilkan 5 file dataset simulasi dummy untuk pengujian rekonsiliasi multi-sumber:
1. 1_mutasi_bank_bca.csv        (Mutasi Rekening Koran BCA KlikBCA Bisnis)
2. 2_tiktok_shop_orders.csv     (Seller Center Order Details TikTok Shop)
3. 3_shopee_settlement.csv      (Seller Center Penghasilan / Saldo Shopee)
4. 4_doku_payment_gateway.csv   (Settlement Report DOKU Payment Gateway)
5. 5_pos_kasir_tunai.csv        (Log Kasir POS Penjualan Tunai Toko)

Semua file terhubung dalam relasi dua arah (Bidirectional):
- Forward: Penjualan/Settlement -> Mutasi Kredit Bank
- Reverse: Mutasi Bank -> Penjualan / Unidentified Deposit / Admin Fee
- Cross-channel: POS <-> DOKU & Shopee
- Discrepancy Terkontrol: In-Transit, Missing Payout, Fee Overcharge, Cash Shortage, Unidentified Credit.
"""

import os
import csv

def generate_sample_datasets(output_dir="sample_data"):
    os.makedirs(output_dir, exist_ok=True)

    # -------------------------------------------------------------
    # 1. TIKTOK SHOP SETTLEMENT REPORT (2_tiktok_shop_orders.csv)
    # -------------------------------------------------------------
    tiktok_file = os.path.join(output_dir, "2_tiktok_shop_orders.csv")
    tiktok_headers = [
        "Statement Date", "Statement ID", "Payment ID", "Status", "Currency",
        "Order ID", "SKU ID", "Quantity", "Order created date", "Gross sales",
        "Seller discount", "Referral fee", "Transaction fee", "Shipping fee",
        "Total settlement amount"
    ]
    tiktok_rows = [
        # Batch 1: TT-STMT-20260801 (Total Net = Rp 1.450.000) -> Cleared to BCA on 2026-08-03
        ["2026-08-01", "TT-STMT-20260801", "PAY-TT-01", "Completed", "IDR", "TT-9901", "SKU-A1", 1, "2026-07-29", 350000, 0, 17500, 7000, 0, 325500],
        ["2026-08-01", "TT-STMT-20260801", "PAY-TT-01", "Completed", "IDR", "TT-9902", "SKU-B2", 2, "2026-07-29", 500000, 20000, 24000, 9600, 0, 446400],
        ["2026-08-01", "TT-STMT-20260801", "PAY-TT-01", "Completed", "IDR", "TT-9903", "SKU-C1", 1, "2026-07-30", 250000, 0, 12500, 5000, 0, 232500],
        ["2026-08-01", "TT-STMT-20260801", "PAY-TT-01", "Completed", "IDR", "TT-9904", "SKU-A2", 1, "2026-07-30", 480000, 0, 24000, 10400, 0, 445600],
        # Batch 2: TT-STMT-20260805 (Total Net = Rp 2.180.000) -> Cleared to BCA on 2026-08-07
        # Note: TT-9907 has FEE OVERCHARGE anomaly (Referral fee 9% instead of 5%)
        ["2026-08-05", "TT-STMT-20260805", "PAY-TT-02", "Completed", "IDR", "TT-9905", "SKU-D1", 2, "2026-08-02", 800000, 0, 40000, 16000, 0, 744000],
        ["2026-08-05", "TT-STMT-20260805", "PAY-TT-02", "Completed", "IDR", "TT-9906", "SKU-B1", 1, "2026-08-03", 600000, 50000, 27500, 11000, 0, 511500],
        ["2026-08-05", "TT-STMT-20260805", "PAY-TT-02", "Completed", "IDR", "TT-9907", "SKU-E1", 1, "2026-08-03", 750000, 0, 67500, 15000, 0, 667500], # Overcharge! 67500 is 9%
        ["2026-08-05", "TT-STMT-20260805", "PAY-TT-02", "Completed", "IDR", "TT-9908", "SKU-A1", 1, "2026-08-04", 280000, 0, 14000, 9000, 0, 257000],
        # Batch 3: TT-STMT-20260810 (Total Net = Rp 1.200.000) -> ANOMALY: MISSING PAYOUT (Not in BCA!)
        ["2026-08-10", "TT-STMT-20260810", "PAY-TT-03", "Completed", "IDR", "TT-9909", "SKU-C2", 2, "2026-08-07", 650000, 0, 32500, 13000, 0, 604500],
        ["2026-08-10", "TT-STMT-20260810", "PAY-TT-03", "Completed", "IDR", "TT-9910", "SKU-A1", 2, "2026-08-08", 640000, 0, 32000, 12500, 0, 595500],
        # Batch 4: TT-STMT-20260814 (Total Net = Rp 850.000) -> ANOMALY: TIMING LAG / IN-TRANSIT (Recent transfer, not yet credited in BCA)
        ["2026-08-14", "TT-STMT-20260814", "PAY-TT-04", "Completed", "IDR", "TT-9911", "SKU-B2", 1, "2026-08-12", 450000, 0, 22500, 9000, 0, 418500],
        ["2026-08-14", "TT-STMT-20260814", "PAY-TT-04", "Completed", "IDR", "TT-9912", "SKU-A1", 1, "2026-08-13", 460000, 0, 23000, 5500, 0, 431500],
    ]
    with open(tiktok_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(tiktok_headers)
        writer.writerows(tiktok_rows)

    # -------------------------------------------------------------
    # 2. SHOPEE SETTLEMENT REPORT (3_shopee_settlement.csv)
    # -------------------------------------------------------------
    shopee_file = os.path.join(output_dir, "3_shopee_settlement.csv")
    shopee_headers = [
        "No. Pesanan", "Waktu Pesanan Selesai", "Harga Asli Produk",
        "Potongan Biaya Administrasi", "Biaya Layanan", "Ongkos Kirim Dibayar Pembeli",
        "Total Penghasilan (Rp)", "No. Penarikan Dana", "Status"
    ]
    shopee_rows = [
        # Batch 1: SHP-WD-8801 (Total Net = Rp 1.850.000) -> Cleared to BCA on 2026-08-04
        ["260801SHP001", "2026-08-02 14:20", 700000, 28000, 14000, 0, 658000, "SHP-WD-8801", "Selesai"],
        ["260801SHP002", "2026-08-02 16:45", 550000, 22000, 11000, 0, 517000, "SHP-WD-8801", "Selesai"],
        ["260802SHP003", "2026-08-03 10:15", 720000, 28800, 16200, 0, 675000, "SHP-WD-8801", "Selesai"],
        # Batch 2: SHP-WD-8802 (Total Net = Rp 2.450.000) -> Cleared to BCA on 2026-08-11
        ["260808SHP004", "2026-08-09 11:30", 1200000, 48000, 24000, 0, 1128000, "SHP-WD-8802", "Selesai"],
        ["260809SHP005", "2026-08-09 18:00", 900000, 36000, 18000, 0, 846000, "SHP-WD-8802", "Selesai"],
        ["260810SHP006", "2026-08-10 09:20", 500000, 20000, 4000, 0, 476000, "SHP-WD-8802", "Selesai"],
        # Batch 3: SHP-WD-8803 (Total Net = Rp 750.000) -> ANOMALY: TIMING LAG / IN-TRANSIT (Withdrawn 2026-08-15)
        ["260813SHP007", "2026-08-14 13:10", 450000, 18000, 9000, 0, 423000, "SHP-WD-8803", "Selesai"],
        ["260814SHP008", "2026-08-14 20:00", 350000, 14000, 9000, 0, 327000, "SHP-WD-8803", "Selesai"],
    ]
    with open(shopee_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(shopee_headers)
        writer.writerows(shopee_rows)

    # -------------------------------------------------------------
    # 3. DOKU PAYMENT GATEWAY REPORT (4_doku_payment_gateway.csv)
    # -------------------------------------------------------------
    doku_file = os.path.join(output_dir, "4_doku_payment_gateway.csv")
    doku_headers = [
        "Invoice ID", "Transaction Date", "Payment Channel", "Payment Status",
        "Gross Amount", "MDR Fee", "Admin Fee", "Net Settlement Amount",
        "Settlement Batch Ref"
    ]
    doku_rows = [
        # Batch 1: DOKU-SETTLE-401 (Total Net = Rp 4.350.000) -> Cleared to BCA on 2026-08-05
        ["INV-20260801-01", "2026-08-01 10:12:00", "BCA Virtual Account", "SUCCESS", 1500000, 0, 4000, 1496000, "DOKU-SETTLE-401"],
        ["INV-20260801-02", "2026-08-01 14:30:15", "Credit Card Visa", "SUCCESS", 2000000, 40000, 2000, 1958000, "DOKU-SETTLE-401"],
        ["INV-20260802-03", "2026-08-02 09:45:00", "QRIS", "SUCCESS", 900000, 2700, 1300, 896000, "DOKU-SETTLE-401"],
        # Batch 2: DOKU-SETTLE-402 (Total Net = Rp 3.120.000) -> Cleared to BCA on 2026-08-12
        ["INV-20260808-04", "2026-08-08 11:20:00", "Mandiri Virtual Account", "SUCCESS", 1200000, 0, 4000, 1196000, "DOKU-SETTLE-402"],
        ["INV-20260809-05", "2026-08-09 15:10:00", "Credit Card Master", "SUCCESS", 1000000, 20000, 2000, 978000, "DOKU-SETTLE-402"],
        ["INV-20260810-06", "2026-08-10 16:40:00", "QRIS", "SUCCESS", 950000, 2850, 1150, 946000, "DOKU-SETTLE-402"],
        # Anomaly: 1 orphan transaction SUCCESS in DOKU, pending batching
        ["INV-20260814-07", "2026-08-14 18:25:00", "QRIS", "SUCCESS", 350000, 1050, 950, 348000, "PENDING_SETTLEMENT"],
    ]
    with open(doku_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(doku_headers)
        writer.writerows(doku_rows)

    # -------------------------------------------------------------
    # 4. POS KASIR TUNAI / TOKO OFFLINE (5_pos_kasir_tunai.csv)
    # -------------------------------------------------------------
    pos_file = os.path.join(output_dir, "5_pos_kasir_tunai.csv")
    pos_headers = [
        "Tanggal", "No Transaksi", "Kasir", "Shift", "Total Belanja",
        "Metode Bayar", "Setor Bank Ref", "Status Setoran", "Catatan"
    ]
    pos_rows = [
        # Day 1: 2026-08-02 - Total Tunai = Rp 2.500.000 -> Setor ke BCA 2026-08-02 (MATCHED)
        ["2026-08-02", "POS-260802-01", "Siti", "Pagi", 1200000, "TUNAI", "SETOR-CDM-0802", "Sudah Disetor", "Lengkap"],
        ["2026-08-02", "POS-260802-02", "Budi", "Siang", 1300000, "TUNAI", "SETOR-CDM-0802", "Sudah Disetor", "Lengkap"],
        # Day 2: 2026-08-06 - Total Tunai = Rp 3.200.000 -> Setor ke BCA 2026-08-07 cuma Rp 3.000.000! (ANOMALY: CASH SHORTAGE Rp 200.000)
        ["2026-08-06", "POS-260806-03", "Siti", "Pagi", 1700000, "TUNAI", "SETOR-CDM-0807", "Sudah Disetor", "Shift pagi"],
        ["2026-08-06", "POS-260806-04", "Budi", "Siang", 1500000, "TUNAI", "SETOR-CDM-0807", "Sudah Disetor", "Selisih fisik kasir Rp 200.000"],
        # Day 3: 2026-08-12 - Total Tunai = Rp 1.950.000 -> Setor ke BCA 2026-08-12 (MATCHED)
        ["2026-08-12", "POS-260812-05", "Rina", "Pagi", 950000, "TUNAI", "SETOR-TELLER-0812", "Sudah Disetor", "Setor via Teller"],
        ["2026-08-12", "POS-260812-06", "Rina", "Siang", 1000000, "TUNAI", "SETOR-TELLER-0812", "Sudah Disetor", "Setor via Teller"],
        # Day 4: 2026-08-15 - Total Tunai = Rp 1.100.000 -> ANOMALY: BELUM DISETOR / FISIK BRANKAS
        ["2026-08-15", "POS-260815-07", "Siti", "Pagi", 1100000, "TUNAI", "BELUM_SETOR", "Dalam Brankas", "Kas toko weekend"],
    ]
    with open(pos_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(pos_headers)
        writer.writerows(pos_rows)

    # -------------------------------------------------------------
    # 5. MUTASI BANK BCA KLIKBCA BISNIS (1_mutasi_bank_bca.csv)
    # -------------------------------------------------------------
    bca_file = os.path.join(output_dir, "1_mutasi_bank_bca.csv")
    bca_headers = ["Tanggal", "Keterangan", "Cabang", "Jumlah", "Tipe", "Saldo"]
    bca_rows = [
        # Opening balance
        ["2026-08-01", "SALDO AWAL", "0000", 25000000, "CR", 25000000],
        # 2026-08-02: Setoran tunai kasir Day 1 -> Matches POS Day 1
        ["2026-08-02", "SETORAN TUNAI CDM KASIR TOKO REF SETOR-CDM-0802", "0123", 2500000, "CR", 27500000],
        # 2026-08-03: TikTok Shop Batch 1 -> Matches TT-STMT-20260801
        ["2026-08-03", "TRSF E-COMM TIKTOK TT-STMT-20260801", "0999", 1450000, "CR", 28950000],
        # 2026-08-04: Shopee Batch 1 -> Matches SHP-WD-8801
        ["2026-08-04", "TRSF SHOPEE PAYOUT SHP-WD-8801", "0998", 1850000, "CR", 30800000],
        # 2026-08-05: DOKU Batch 1 -> Matches DOKU-SETTLE-401
        ["2026-08-05", "SETTLEMENT DOKU PG DOKU-SETTLE-401", "0995", 4350000, "CR", 35150000],
        # 2026-08-07: TikTok Shop Batch 2 -> Matches TT-STMT-20260805
        ["2026-08-07", "TRSF E-COMM TIKTOK TT-STMT-20260805", "0999", 2180000, "CR", 37330000],
        # 2026-08-07: Setoran kasir Day 2 (Shortage Rp 200rb) -> Matches POS Day 2
        ["2026-08-07", "SETORAN TUNAI CDM KASIR TOKO REF SETOR-CDM-0807", "0123", 3000000, "CR", 40330000],
        # 2026-08-08: REVERSE ANOMALY: UNIDENTIFIED BANK DEPOSIT (No order/invoice match!)
        ["2026-08-08", "TRSF E-BANKING CR 08/08 98231 BPK BUDI HANDOKO", "0145", 2500000, "CR", 42830000],
        # 2026-08-10: REVERSE ANOMALY: Bunga Bank belum dicatat di buku internal
        ["2026-08-10", "BUNGA REKENING GIRO AGUSTUS 2026", "0000", 45200, "CR", 42875200],
        # 2026-08-11: Shopee Batch 2 -> Matches SHP-WD-8802
        ["2026-08-11", "TRSF SHOPEE PAYOUT SHP-WD-8802", "0998", 2450000, "CR", 45325200],
        # 2026-08-12: DOKU Batch 2 -> Matches DOKU-SETTLE-402
        ["2026-08-12", "SETTLEMENT DOKU PG DOKU-SETTLE-402", "0995", 3120000, "CR", 48445200],
        # 2026-08-12: Setoran kasir Day 3 -> Matches POS Day 3
        ["2026-08-12", "SETORAN TUNAI TELLER CABANG REF SETOR-TELLER-0812", "0123", 1950000, "CR", 50395200],
        # 2026-08-15: REVERSE ANOMALY: Biaya Admin Bank belum dicatat
        ["2026-08-15", "BIAYA ADM REK KORAN AGUSTUS 2026", "0000", 25000, "DB", 50370200],
        # 2026-08-15: REVERSE ANOMALY: Pajak Bunga Bank belum dicatat
        ["2026-08-15", "PAJAK BUNGA GIRO 20%", "0000", 9040, "DB", 50361160],
    ]
    with open(bca_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(bca_headers)
        writer.writerows(bca_rows)

    # -------------------------------------------------------------
    # 6. MUTASI BANK BCA FORMAT PDF (1_mutasi_bank_bca_sample.pdf)
    # -------------------------------------------------------------
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    pdf_file = os.path.join(output_dir, "1_mutasi_bank_bca_sample.pdf")
    doc = SimpleDocTemplate(pdf_file, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    p_title = ParagraphStyle('BcaTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor('#003399'))
    p_norm = ParagraphStyle('BcaNorm', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#1F2937'))
    p_bold = ParagraphStyle('BcaBold', parent=p_norm, fontName='Helvetica-Bold')

    pdf_elements = []
    pdf_elements.append(Paragraph("<b>PT BANK CENTRAL ASIA TBK</b>", p_title))
    pdf_elements.append(Paragraph("REKENING KORAN GIRO BISNIS / E-STATEMENT", p_bold))
    pdf_elements.append(Paragraph("No. Rekening: 8820-192-881 | Nama: PT REKON AUTO INDONESIA | Periode: 01/08/2026 - 15/08/2026 | Valuta: IDR", p_norm))
    pdf_elements.append(Spacer(1, 6))
    pdf_elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#003399'), spaceBefore=2, spaceAfter=8))

    tbl_headers = [
        Paragraph("<b>TANGGAL</b>", p_bold),
        Paragraph("<b>KETERANGAN TRANSAKSI</b>", p_bold),
        Paragraph("<b>CAB</b>", p_bold),
        Paragraph("<b>JUMLAH (IDR)</b>", p_bold),
        Paragraph("<b>TIPE</b>", p_bold),
        Paragraph("<b>SALDO (IDR)</b>", p_bold)
    ]
    tbl_data = [tbl_headers]
    for r in bca_rows:
        tbl_data.append([
            Paragraph(r[0], p_norm),
            Paragraph(r[1], p_norm),
            Paragraph(r[2], p_norm),
            Paragraph(f"{r[3]:,.0f}", p_norm),
            Paragraph(r[4], p_bold),
            Paragraph(f"{r[5]:,.0f}", p_norm)
        ])

    t_bca = Table(tbl_data, colWidths=[65, 230, 35, 75, 35, 80])
    t_bca.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    pdf_elements.append(t_bca)
    doc.build(pdf_elements)

    print(f"[OK] Berhasil membuat seluruh data simulasi di folder '{output_dir}':")
    print(f"  1. {bca_file}")
    print(f"  2. {tiktok_file}")
    print(f"  3. {shopee_file}")
    print(f"  4. {doku_file}")
    print(f"  5. {pos_file}")
    print(f"  6. {pdf_file} (Rekening Koran PDF)")

if __name__ == "__main__":
    generate_sample_datasets()
