"""
generate_docs_pdf.py
--------------------
Skrip Generator Dokumentasi Lengkap & Komprehensif ReconAuto.ID (Versi v1.0.0).
Menghasilkan dokumen resmi berkualitas cetak (A4) yang mencakup:
1. Ringkasan Eksekutif & Latar Belakang Masalah Finansial
2. Arsitektur Perangkat Lunak & Pola Adapter Strategy Pattern
3. Metodologi Rekonsiliasi Dua Arah & Formula Proof of Cash (Rp 0.00)
4. Rekonsiliasi Tiga Arah COD Ekspedisi (AWB JNE & SiCepat)
5. Fitur AI Chatbot Cerdas ReconBot (Google Gemini) & Eskalasi Customer Service
6. Persistensi Basis Data SQLite rekonsile.db & Rolling Reconciliation
7. Manajemen Sengketa (Dispute Claim PDF) & Integrasi Akuntansi (Jurnal/Accurate/SAP)
8. Spesifikasi REST API & Laporan Hasil Pengujian Otomatis (100% PASS)
9. Panduan Operasional Standar (SOP) Pengguna & Pemeliharaan Database
"""

import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Palette Warna Modern & Profesional (Theme ReconAuto)
C_NAVY_DARK  = colors.HexColor("#0F172A")  # Slate 900
C_NAVY_MED   = colors.HexColor("#1E293B")  # Slate 800
C_BLUE_MAIN  = colors.HexColor("#2563EB")  # Blue 600
C_BLUE_DARK  = colors.HexColor("#1D4ED8")  # Blue 700
C_BLUE_LIGHT = colors.HexColor("#EFF6FF")  # Blue 50
C_EMERALD    = colors.HexColor("#059669")  # Emerald 600
C_EMERALD_BG = colors.HexColor("#ECFDF5")  # Emerald 50
C_AMBER      = colors.HexColor("#D97706")  # Amber 600
C_AMBER_BG   = colors.HexColor("#FFFBEB")  # Amber 50
C_ROSE       = colors.HexColor("#E11D48")  # Rose 600
C_ROSE_BG    = colors.HexColor("#FFF1F2")  # Rose 50
C_PURPLE     = colors.HexColor("#7C3AED")  # Violet 600
C_PURPLE_BG  = colors.HexColor("#F5F3FF")  # Violet 50
C_SLATE_TXT  = colors.HexColor("#334155")  # Slate 700
C_SLATE_MUT  = colors.HexColor("#64748B")  # Slate 500
C_BORDER     = colors.HexColor("#CBD5E1")  # Slate 300
C_BG_ALT     = colors.HexColor("#F8FAFC")  # Slate 50
C_WHITE      = colors.HexColor("#FFFFFF")

class NumberedCanvas(canvas.Canvas):
    """Canvas kustom untuk nomor halaman dinamis (Halaman X dari Y) dan header/footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, total_pages):
        page_w, page_h = A4
        if self._pageNumber == 1:
            # Halaman Cover: gambar dekorasi aksen kiri
            self.saveState()
            self.setFillColor(C_BLUE_MAIN)
            self.rect(0, 0, 14, page_h, fill=1, stroke=0)
            self.setFillColor(C_NAVY_DARK)
            self.rect(14, 0, 8, page_h, fill=1, stroke=0)
            self.restoreState()
            return

        self.saveState()
        # Running Header
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(C_BLUE_MAIN)
        self.drawString(40, page_h - 28, "ReconAuto.ID")
        self.setFont("Helvetica", 8)
        self.setFillColor(C_SLATE_MUT)
        self.drawString(102, page_h - 28, "|   Dokumentasi Pengetahuan & Panduan Operasional Sistem (v1.0.0)")

        self.setStrokeColor(C_BORDER)
        self.setLineWidth(0.5)
        self.line(40, page_h - 32, page_w - 40, page_h - 32)

        # Running Footer
        self.line(40, 36, page_w - 40, 36)
        self.setFont("Helvetica", 8)
        self.setFillColor(C_SLATE_MUT)
        self.drawString(40, 24, "Dokumen Resmi Pengetahuan Finansial & Audit Internal — PT Rekon Auto Retail")
        
        page_str = f"Halaman {self._pageNumber} dari {total_pages}"
        self.drawRightString(page_w - 40, 24, page_str)
        self.restoreState()

def build_pdf(filename="Dokumentasi_Lengkap_ReconAuto_ID.pdf"):
    pdf_path = os.path.abspath(filename)
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()

    # Kustomisasi Typography Styles
    style_cover_title = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=C_NAVY_DARK,
        spaceAfter=8
    )

    style_cover_subtitle = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=C_SLATE_TXT,
        spaceAfter=20
    )

    style_meta_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=C_NAVY_DARK
    )

    style_meta_val = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=C_SLATE_TXT
    )

    style_h1 = ParagraphStyle(
        'CustomH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=C_NAVY_DARK,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    style_h2 = ParagraphStyle(
        'CustomH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=C_BLUE_MAIN,
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True
    )

    style_h3 = ParagraphStyle(
        'CustomH3',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=C_NAVY_MED,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )

    style_body = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=C_SLATE_TXT,
        spaceAfter=5
    )

    style_body_bold = ParagraphStyle(
        'CustomBodyBold',
        parent=style_body,
        fontName='Helvetica-Bold',
        textColor=C_NAVY_DARK
    )

    style_bullet = ParagraphStyle(
        'CustomBullet',
        parent=style_body,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=2.5
    )

    style_code = ParagraphStyle(
        'CustomCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0F172A")
    )

    style_th = ParagraphStyle(
        'TH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=C_WHITE,
        alignment=1
    )

    style_td = ParagraphStyle(
        'TD',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=C_SLATE_TXT
    )

    style_td_mono = ParagraphStyle(
        'TDMono',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9.5,
        textColor=C_NAVY_DARK
    )

    style_callout_title = ParagraphStyle(
        'CalloutTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=C_BLUE_DARK
    )

    style_callout_body = ParagraphStyle(
        'CalloutBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=C_SLATE_TXT
    )

    story = []

    def make_callout(title_text, body_text, bg_color=C_BLUE_LIGHT, border_color=C_BLUE_MAIN):
        p_title = Paragraph(f"<b>{title_text}</b>", style_callout_title)
        p_body = Paragraph(body_text, style_callout_body)
        box_table = Table([[p_title], [p_body]], colWidths=[515])
        box_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_color),
            ('BOX', (0, 0), (-1, -1), 1, border_color),
            ('PADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
            ('TOPPADDING', (0, 1), (-1, 1), 2),
        ]))
        return box_table

    # =========================================================================
    # HALAMAN COVER
    # =========================================================================
    story.append(Spacer(1, 30))
    story.append(Paragraph("DOKUMENTASI TEKNIS & PANDUAN OPERASIONAL SISTEM", ParagraphStyle(
        'CoverKicker',
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=C_BLUE_MAIN,
        spaceAfter=6
    )))
    story.append(Paragraph("ReconAuto.ID — Platform Rekonsiliasi Finansial Multi-Sumber, Audit 3-Arah COD & Asisten AI", style_cover_title))
    story.append(Paragraph("Dokumentasi Komprehensif Arsitektur Adapter, Multi-Bank Statement, Rekonsiliasi 3-Arah Kurir Logistik, Persistensi SQLite, Rekonsiliasi Bergulir (*Rolling Reconciliation*), Integrasi Google Gemini AI & Eskalasi Customer Service.", style_cover_subtitle))

    story.append(HRFlowable(width="100%", thickness=2, color=C_BLUE_MAIN, spaceAfter=16))

    meta_data = [
        [Paragraph("Nomor Dokumen", style_meta_label), Paragraph("DOC-RECONAUTO-V1.0-ID", style_meta_val)],
        [Paragraph("Versi Rilis Resmi", style_meta_label), Paragraph("<b>v1.0.0 (Production Master Release)</b>", style_meta_val)],
        [Paragraph("Status Kelulusan Uji", style_meta_label), Paragraph("<b>100% Lulus Uji Otomatis (All 6 Suites PASS)</b>", style_meta_val)],
        [Paragraph("Tanggal Penerbitan", style_meta_label), Paragraph("September 2026", style_meta_val)],
        [Paragraph("Klasifikasi Akses", style_meta_label), Paragraph("Dokumen Resmi / Tim Keuangan, Auditor Internal, & Rekayasa Perangkat Lunak", style_meta_val)],
        [Paragraph("Basis Data Lokal", style_meta_label), Paragraph("SQLite 3 (<code>rekonsile.db</code>) — Penyimpanan Mandiri & Lintas Periode", style_meta_val)],
        [Paragraph("Kecerdasan Buatan (AI)", style_meta_label), Paragraph("Google Gemini AI (<code>gemini-3.6-flash</code>) & Eskalasi CS WhatsApp (+62 815-3617-5933)", style_meta_val)],
        [Paragraph("Tumpukan Teknologi", style_meta_label), Paragraph("Python 3.14, FastAPI, ReportLab 5.0, SQLite3, Alpine.js, Tailwind CSS", style_meta_val)]
    ]
    meta_table = Table(meta_data, colWidths=[150, 365])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_BG_ALT),
        ('BOX', (0, 0), (-1, -1), 1, C_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 20))
    story.append(make_callout(
        "Kesiapan & Status Operasional Sistem (v1.0.0)",
        "ReconAuto.ID telah beroperasi penuh pada alamat lokal <b>http://127.0.0.1:8000</b>. Seluruh mekanisme persistensi sesi, pembuktian kas matematis (Proof of Cash selisih <b>Rp 0.00</b>), audit 3-arah kurir ekspedisi COD, pelacakan dana bergulir (*rolling reconciliation*), generator surat klaim sengketa PDF, ekspor workbook audit Excel, dan asisten percakapan cerdas ReconBot AI terbukti aktif dan teruji 100% lulus.",
        C_EMERALD_BG,
        C_EMERALD
    ))

    story.append(PageBreak())

    # =========================================================================
    # DAFTAR ISI & BAB 1: RINGKASAN EKSEKUTIF
    # =========================================================================
    story.append(Paragraph("Daftar Isi Dokumen", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=8))

    toc_data = [
        [Paragraph("<b>Bab 1</b>", style_body_bold), Paragraph("Ringkasan Eksekutif & 5 Fenomena Risiko Kebocoran Kas Finansial", style_body)],
        [Paragraph("<b>Bab 2</b>", style_body_bold), Paragraph("Arsitektur Perangkat Lunak & Pola Adapter Strategy Pattern (core/parsers)", style_body)],
        [Paragraph("<b>Bab 3</b>", style_body_bold), Paragraph("Metodologi Rekonsiliasi Dua Arah & Formula Proof of Cash (Rp 0.00)", style_body)],
        [Paragraph("<b>Bab 4</b>", style_body_bold), Paragraph("Rekonsiliasi Tiga Arah COD Ekspedisi (JNE & SiCepat Express AWB)", style_body)],
        [Paragraph("<b>Bab 5</b>", style_body_bold), Paragraph("Fitur AI Chatbot ReconBot (Google Gemini) & Eskalasi Customer Service", style_body)],
        [Paragraph("<b>Bab 6</b>", style_body_bold), Paragraph("Persistensi Basis Data SQLite (rekonsile.db) & Rekonsiliasi Bergulir", style_body)],
        [Paragraph("<b>Bab 7</b>", style_body_bold), Paragraph("Manajemen Sengketa (Dispute Claim PDF) & Integrasi Akuntansi (ERP/GL)", style_body)],
        [Paragraph("<b>Bab 8</b>", style_body_bold), Paragraph("Spesifikasi Lengkap REST API & Laporan Bukti Kelulusan Uji (100% PASS)", style_body)],
        [Paragraph("<b>Bab 9</b>", style_body_bold), Paragraph("Panduan Operasional Standar (SOP) Pengguna, Kasir, & Auditor", style_body)]
    ]
    toc_table = Table(toc_data, colWidths=[60, 455])
    toc_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, C_BG_ALT),
        ('PADDING', (0, 0), (-1, -1), 3.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(toc_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Bab 1: Ringkasan Eksekutif & 5 Risiko Finansial", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("1.1 Latar Belakang Kompleksitas Omni-Channel di Indonesia", style_h2))
    story.append(Paragraph(
        "Di era perdagangan modern dan ritel multi-kanal Indonesia, perusahaan wajib menerima pembayaran dari berbagai saluran secara simultan: <b>Marketplace E-Commerce</b> (TikTok Shop, Shopee), <b>Payment Gateway</b> (DOKU, Xendit), kasir toko fisik (<b>POS Tunai</b>), dan layanan <b>Cash on Delivery (COD)</b> melalui kurir 3PL (JNE, SiCepat). Seluruh dana tersebut bermuara ke rekening koran berbagai bank operasional (BCA, Mandiri, BNI, BRI).",
        style_body
    ))
    story.append(Paragraph(
        "Proses rekonsiliasi manual menggunakan spreadsheet seringkali runtuh karena volume ribuan pesanan harian yang dicairkan secara kolektif (*batch settlement*), susunan kolom berkas yang berlainan dari tiap penyedia, serta potongan komisi platform yang kompleks.",
        style_body
    ))

    story.append(Paragraph("1.2 Lima Fenomena Risiko Kebocoran Kas Nyata", style_h2))
    story.append(Paragraph(
        "ReconAuto.ID dirancang secara spesifik untuk memitigasi lima titik kebocoran kas kritis:",
        style_body
    ))

    risk_data = [
        [Paragraph("Jenis Risiko", style_th), Paragraph("Mekanisme Terjadinya Masalah", style_th), Paragraph("Dampak Terhadap Pembukuan Kas", style_th)],
        [
            Paragraph("<b>Timing Lag / Cut-Off Period</b>", style_td),
            Paragraph("Pencairan dana marketplace/PG memerlukan waktu kliring 1-3 hari kerja (T+3). Transaksi akhir bulan baru masuk rekening bulan berikutnya.", style_td),
            Paragraph("Saldo kas buku besar tidak sama dengan bank saat tutup buku; rawan salah catat sebagai piutang macet.", style_td)
        ],
        [
            Paragraph("<b>Platform Fee Overcharge</b>", style_td),
            Paragraph("Marketplace memotong komisi lebih tinggi daripada tarif kontrak (misal: kontrak 6%, namun riil dipotong 8.5%).", style_td),
            Paragraph("Pengikisan margin keuntungan bersih secara tersembunyi tanpa disadari pemilik usaha.", style_td)
        ],
        [
            Paragraph("<b>Missing Payouts / Silent Failures</b>", style_td),
            Paragraph("Order berstatus selesai (Delivered) dan saldo merchant berkurang, namun bank statement tidak pernah menerima transfer dana.", style_td),
            Paragraph("Kerugian nyata (*cash leakage*) yang hangus jika tidak diklaim dalam batas waktu SLA sengketa 30 hari.", style_td)
        ],
        [
            Paragraph("<b>Kasir Toko Fisik Shortage</b>", style_td),
            Paragraph("Selisih hitung fisik uang tunai di laci kasir saat disetorkan ke mesin CDM atau teller bank.", style_td),
            Paragraph("Selisih kas di tangan (*cash in drawer*) yang tidak tercatat akuntansinya.", style_td)
        ],
        [
            Paragraph("<b>Kebocoran Kas COD Ekspedisi</b>", style_td),
            Paragraph("Kurir ekspedisi belum menyetor uang tagihan barang COD yang sudah diterima pembeli (*unremitted*) atau menyetor lebih kecil (*shortage*).", style_td),
            Paragraph("Kesenjangan finansial paling kritis dalam bisnis ritel yang mencapai 3-8% dari omzet penjualan COD.", style_td)
        ]
    ]
    t_risk = Table(risk_data, colWidths=[115, 205, 195])
    t_risk.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY_MED),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_BG_ALT]),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(t_risk)

    story.append(PageBreak())

    # =========================================================================
    # BAB 2: ARSITEKTUR PERANGKAT LUNAK & ADAPTER STRATEGY PATTERN
    # =========================================================================
    story.append(Paragraph("Bab 2: Arsitektur Perangkat Lunak & Strategy Pattern", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("2.1 Prinsip Desain Adapter & Registry Otomatis", style_h2))
    story.append(Paragraph(
        "Untuk menangani keanekaragaman format berkas tanpa mengubah kode logika inti (*Open-Closed Principle*), ReconAuto.ID mengadopsi <b>Pola Desain Adapter (Strategy Pattern)</b> yang dikelola oleh <code>core/parsers/registry.py</code>. Setiap format saluran memiliki kelas adapter turunan dari <code>BaseChannelParser</code> yang menyediakan mekanisme deteksi format cerdas (*auto-detection*).",
        style_body
    ))

    arch_data = [
        [Paragraph("Kategori Saluran", style_th), Paragraph("Modul Parser Adapter", style_th), Paragraph("Format & Penyedia yang Didukung", style_th)],
        [
            Paragraph("<b>Perbankan (Multi-Bank)</b>", style_td),
            Paragraph("<code>bank/bca_parser.py</code><br/><code>bank/mandiri_parser.py</code><br/><code>bank/bni_parser.py</code><br/><code>bank/bri_parser.py</code><br/><code>bank/mt940_parser.py</code>", style_td_mono),
            Paragraph("• Bank BCA (KlikBCA Bisnis CSV & e-Statement PDF)<br/>• Bank Mandiri (Kopra by Mandiri / MCM CSV)<br/>• Bank BNI (BNI Direct Giro CSV)<br/>• Bank BRI (Cash Management System CSV)<br/>• Standar Global SWIFT MT940 (.sta / .mt940)", style_td)
        ],
        [
            Paragraph("<b>Marketplace E-Commerce</b>", style_td),
            Paragraph("<code>marketplace/tiktok_parser.py</code><br/><code>marketplace/shopee_parser.py</code>", style_td_mono),
            Paragraph("• TikTok Shop Seller Center Settlement CSV<br/>• Shopee Seller Centre (Penghasilan Saya) CSV", style_td)
        ],
        [
            Paragraph("<b>Payment Gateway</b>", style_td),
            Paragraph("<code>payment_gateway/doku_parser.py</code>", style_td_mono),
            Paragraph("• DOKU Payment Gateway Settlement CSV (Virtual Account, QRIS, Kartu Kredit)", style_td)
        ],
        [
            Paragraph("<b>Kasir Ritel (POS)</b>", style_td),
            Paragraph("<code>pos/pos_cash_parser.py</code>", style_td_mono),
            Paragraph("• Rekap Kasir POS Ritel Harian CSV (Pelacakan Uang Fisik Laci Toko)", style_td)
        ],
        [
            Paragraph("<b>Kurir Logistik COD (3PL)</b>", style_td),
            Paragraph("<code>logistics/jne_cod_parser.py</code><br/><code>logistics/sicepat_cod_parser.py</code>", style_td_mono),
            Paragraph("• JNE Express COD Settlement Manifest CSV<br/>• SiCepat Express COD Settlement Report CSV", style_td)
        ]
    ]
    t_arch = Table(arch_data, colWidths=[120, 165, 230])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY_MED),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_BG_ALT]),
        ('PADDING', (0, 0), (-1, -1), 4.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(t_arch)

    story.append(Spacer(1, 8))
    story.append(Paragraph("2.2 Kompatibilitas Fasad Mundur (Backward Compatibility)", style_h2))
    story.append(Paragraph(
        "Seluruh pemanggilan dari endpoint aplikasi tetap mengakses modul <code>core/parser.py</code> sebagai fasad tingkat tinggi (*High-Level Facade*). Fasad ini mendelegasikan pemeriksaan berkas ke <code>default_registry</code>, sehingga pembaruan adapter perbankan baru tidak pernah merusak kode rekonsiliasi yang sudah ada.",
        style_body
    ))

    story.append(PageBreak())

    # =========================================================================
    # BAB 3: METODOLOGI REKONSILIASI DUA ARAH & FORMULA PROOF OF CASH
    # =========================================================================
    story.append(Paragraph("Bab 3: Rekonsiliasi Dua Arah & Formula Proof of Cash", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("3.1 Metodologi Pencocokan Dua Arah (Bidirectional Matching)", style_h2))
    story.append(Paragraph(
        "Sistem menjalankan audit rekonsiliasi simultan dari dua perspektif:",
        style_body
    ))
    story.append(Paragraph("1. <b>Arah Sumber ke Bank (Source-to-Bank):</b> Setiap batch pencairan dari TikTok, Shopee, DOKU, dan setoran kasir dicocokkan ke mutasi kredit bank melalui nomor referensi batch ID dan toleransi nominal.", style_bullet))
    story.append(Paragraph("2. <b>Arah Bank ke Sumber (Bank-to-Source):</b> Setiap baris kredit rekening koran bank ditelusuri ke belakang untuk memastikan memiliki dasar transaksi yang sah, memisahkan pendapatan bunga bank, dan mendeteksi transfer tidak dikenal (*unidentified deposit*).", style_bullet))

    story.append(Paragraph("3.2 Formula Matematis Proof of Cash (Keseimbangan Rp 0.00)", style_h2))
    story.append(Paragraph(
        "Pilar akuntabilitas keuangan ReconAuto.ID terletak pada pembuktian kas matematis tanpa kompromi:",
        style_body
    ))

    proof_box = [
        [Paragraph("<b>FORMULA PEMBUKTIAN KESEIMBANGAN KAS (PROOF OF CASH)</b>", style_callout_title)],
        [Paragraph(
            "<b>Total Kredit Mutasi Bank</b> = <br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>Total Penjualan Bersih (Net Sales)</b><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>- Dana In-Transit Periode Berjalan (Timing Lag)</b><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>- Selisih Pencairan Tertahan (Missing Payout)</b><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>- Kas Fisik Toko yang Belum Disetor (Cash in Drawer)</b><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>- Selisih Kekurangan Fisik Kasir (Shortage)</b><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>+ Pelunasan Dana In-Transit Periode Lampau (Rolling Resolved)</b><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>+ Pencairan Dana COD Ekspedisi yang Masuk Bank (COD Cleared)</b><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>+ Pendapatan Bunga Bank Bersih (Net Bank Interest)</b><br/>"
            "&nbsp;&nbsp;&nbsp;&nbsp;<b>+ Setoran Tak Dikenal (Unidentified Deposit)</b><br/><br/>"
            "<b>Kondisi Keseimbangan:</b> <code>Variance = Abs(Total Kredit Bank - Total Rekonsiliasi) == Rp 0.00 (Balanced: True)</code>",
            style_callout_body
        )]
    ]
    t_proof = Table(proof_box, colWidths=[515])
    t_proof.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_BLUE_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1.5, C_BLUE_MAIN),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_proof)

    story.append(Spacer(1, 8))
    story.append(Paragraph("3.3 Penanganan Bunga, Pajak, dan Biaya Administrasi Bank", style_h2))
    story.append(Paragraph(
        "Sistem secara otomatis mengekstraksi kredit bunga bank (kode mutasi <code>KREDIT BUNGA</code>) dan mendebet pajak bunga (PPh Pasal 4 ayat 2) serta biaya administrasi rekening bank korporat. Seluruh penyesuaian ini dimasukkan ke dalam draf jurnal umum (*General Ledger*) secara berpasangan.",
        style_body
    ))

    story.append(PageBreak())

    # =========================================================================
    # BAB 4: REKONSILIASI TIGA ARAH COD EKSPEDISI (3-WAY MATCHING)
    # =========================================================================
    story.append(Paragraph("Bab 4: Rekonsiliasi 3-Arah COD Ekspedisi (JNE & SiCepat)", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("4.1 Kesenjangan Finansial Kritis pada Layanan COD", style_h2))
    story.append(Paragraph(
        "Layanan *Cash on Delivery* (COD) menyumbang volume besar transaksi retail online, namun menyimpan risiko kebocoran tertinggi. Uang tunai dari pembeli ditagih oleh kurir lapangan, dihimpun oleh hub ekspedisi, baru kemudian ditransfer ke rekening bank penjual dengan potongan biaya penanganan COD (biasanya 2-3%). Kebocoran sering terjadi jika kurir menunda penyetoran dana atau memotong biaya retensi secara berlebihan.",
        style_body
    ))

    story.append(Paragraph("4.2 Alur Audit 3-Arah (Tripartite Matching Workflow)", style_h2))
    story.append(Paragraph(
        "ReconAuto.ID menerapkan audit rekonsiliasi tiga arah yang menghubungkan:",
        style_body
    ))
    story.append(Paragraph("• <b>Titik 1 - Order Penjualan:</b> ID Pesanan dan Nilai Tagihan Barang COD.", style_bullet))
    story.append(Paragraph("• <b>Titik 2 - Manifest Kurir (AWB):</b> Nomor Resi Kurir (JNE/SiCepat), Status Pengiriman (*Delivered*), Biaya Layanan Kurir, dan Nilai Net Pencairan (*Net Remitted*).", style_bullet))
    story.append(Paragraph("• <b>Titik 3 - Mutasi Kredit Bank:</b> Nomor Referensi Transfer Kurir (misal: <code>JNE-TRF-001</code>) pada rekening koran Bank Mandiri atau BCA.", style_bullet))

    cod_status_data = [
        [Paragraph("Status Hasil Audit", style_th), Paragraph("Indikator & Kondisi", style_th), Paragraph("Aksi Korektif Sistem & Audit Trail", style_th)],
        [
            Paragraph("<b>MATCHED / CLEARED</b>", style_td),
            Paragraph("Nomor AWB cocok dengan Order, dan nominal Net Pencairan kurir tepat masuk ke mutasi kredit bank.", style_td),
            Paragraph("Ditandai lunas, dicatat ke tabel <code>stored_cod_settlements</code>, dan dimasukkan ke Proof of Cash sebagai dana klop.", style_td)
        ],
        [
            Paragraph("<b>COD_UNREMITTED (Bahaya)</b>", style_td),
            Paragraph("Paket terkonfirmasi *Delivered* oleh kurir, namun dana setoran belum masuk ke rekening bank melewati batas SLA (T+3 hari).", style_td),
            Paragraph("Diterbitkan peringatan kebocoran dana tertahan; disiapkan draf surat klaim sengketa kurir otomatis.", style_td)
        ],
        [
            Paragraph("<b>COD_SHORTAGE (Bahaya)</b>", style_td),
            Paragraph("Kurir menyetorkan dana, namun jumlah bersih yang masuk ke rekening bank lebih kecil daripada tagihan COD barang.", style_td),
            Paragraph("Dicatat sebagai anomali kekurangan setor; nilai selisih ditagihkan kembali ke pihak ekspedisi.", style_td)
        ]
    ]
    t_cod = Table(cod_status_data, colWidths=[125, 195, 195])
    t_cod.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY_MED),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_BG_ALT]),
        ('PADDING', (0, 0), (-1, -1), 4.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(t_cod)

    story.append(PageBreak())

    # =========================================================================
    # BAB 5: FITUR AI CHATBOT RECONBOT (GOOGLE GEMINI) & CUSTOMER SERVICE
    # =========================================================================
    story.append(Paragraph("Bab 5: Fitur AI Chatbot ReconBot & Eskalasi CS", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("5.1 Integrasi Google Gemini AI (Model gemini-3.6-flash)", style_h2))
    story.append(Paragraph(
        "ReconAuto.ID dilengkapi dengan asisten AI percakapan cerdas bernama <b>ReconBot</b> yang ditenagai oleh model generasi terbaru Google Gemini (<code>gemini-3.6-flash</code>). Asisten ini tertanam langsung di pojok kanan bawah antarmuka web melalui tombol mengambang (*floating widget*).",
        style_body
    ))
    story.append(Paragraph("• <b>Basis Pengetahuan Luas:</b> Memahami seluruh seluk-beluk fitur aplikasi, formula Proof of Cash, audit COD 3-arah, cara impor data, dan anomali keuangan.", style_bullet))
    story.append(Paragraph("• <b>Fleksibilitas Menjawab:</b> Mampu menjawab segala pertanyaan umum seputar akuntansi ritel, perpajakan, bisnis e-commerce, maupun percakapan santai secara luwes.", style_bullet))
    story.append(Paragraph("• <b>Format Bersih:</b> Dilengkapi filter sanitasi otomatis (<code>clean_chatbot_reply</code>) yang melenyapkan simbol mentah LaTeX ($$, \\text{}) dan tanda pagar markdown (###) sehingga pesan selalu tersaji rapi dengan teks tebal dan poin-poin.", style_bullet))

    story.append(Paragraph("5.2 Pengalihan Proaktif ke Customer Service (CS WhatsApp)", style_h2))
    story.append(Paragraph(
        "Apabila pengguna membutuhkan bantuan staf manusia, mengalami kendala operasional khusus, atau menanyakan kontak admin/sales:",
        style_body
    ))
    story.append(Paragraph("1. Sistem secara otomatis mendeteksi kata kunci: <code>cs</code>, <code>customer service</code>, <code>admin</code>, <code>whatsapp</code>, <code>komplain</code>, atau <code>telepon</code>.", style_bullet))
    story.append(Paragraph("2. AI memberikan tanggapan empati dan menampilkan <b>Kartu Aksi Hijau Interaktif</b> berisi tombol langsung ke WhatsApp Customer Support resmi: <br/><code>https://wa.me/6281234567890?text=Halo%20CS%20ReconAuto.ID...</code>", style_bullet))
    story.append(Paragraph("3. Menyediakan informasi kontak alternatif via email resmi <code>support@reconauto.id</code> dan jam operasional (Senin-Jumat 08:00 - 17:00 WIB).", style_bullet))

    story.append(Paragraph("5.3 Fitur Antarmuka Chatbot Interaktif", style_h2))

    chat_ui_data = [
        [Paragraph("Komponen Antarmuka", style_th), Paragraph("Fungsi & Perilaku Pengguna", style_th)],
        [
            Paragraph("<b>Floating Action Button</b>", style_td),
            Paragraph("Tombol melayang di pojok kanan bawah dengan gradien ungu-indigo, ikon robot, dan indikator denyut hijau online.", style_td)
        ],
        [
            Paragraph("<b>Quick Suggestion Chips</b>", style_td),
            Paragraph("Tombol pertanyaan pintas 1-klik: <i>Apa itu Proof of Cash?</i>, <i>Audit COD 3-Arah</i>, <i>Hubungi CS WhatsApp</i>, dan <i>⚡ Cara Pakai Demo</i>.", style_td)
        ],
        [
            Paragraph("<b>Tombol Pintas Header 'CS WhatsApp'</b>", style_td),
            Paragraph("Tombol permanen di bagian atas jendela percakapan untuk langsung membuka percakapan WhatsApp CS kapan pun tanpa perlu mengetik.", style_td)
        ],
        [
            Paragraph("<b>Typing Indicator Animation</b>", style_td),
            Paragraph("Animasi 3 titik memantul yang memberi umpan balik visual saat ReconBot sedang merumuskan jawaban dari server AI.", style_td)
        ]
    ]
    t_chat_ui = Table(chat_ui_data, colWidths=[160, 355])
    t_chat_ui.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY_MED),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_BG_ALT]),
        ('PADDING', (0, 0), (-1, -1), 4.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(t_chat_ui)

    story.append(PageBreak())

    # =========================================================================
    # BAB 6: PERSISTENSI SQLITE & REKONSILIASI BERGULIR
    # =========================================================================
    story.append(Paragraph("Bab 6: Basis Data SQLite & Rolling Reconciliation", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("6.1 Arsitektur Basis Data Relasional Lokal (rekonsile.db)", style_h2))
    story.append(Paragraph(
        "ReconAuto.ID menyimpan seluruh jejak audit secara lokal tanpa ketergantungan server database eksternal melalui berkas <code>rekonsile.db</code>. Struktur tabel mencakup:",
        style_body
    ))

    db_tables = [
        [Paragraph("Nama Tabel SQLite", style_th), Paragraph("Entitas yang Disimpan", style_th), Paragraph("Fungsi Kunci dalam Audit Trail", style_th)],
        [
            Paragraph("<code>reconciliation_runs</code>", style_td_mono),
            Paragraph("Metadata Sesi Audit", style_td),
            Paragraph("Mencatat ID Sesi (<code>RUN-YYYYMMDD-...</code>), tanggal eksekusi, total transaksi, total kredit bank, status keseimbangan, dan variance.", style_td)
        ],
        [
            Paragraph("<code>stored_batches</code>", style_td_mono),
            Paragraph("Batch Payout Marketplace/PG", style_td),
            Paragraph("Menyimpan rincian settlement kolektif, status rekonsiliasi, dan pelacakan status in-transit lintas periode.", style_td)
        ],
        [
            Paragraph("<code>stored_transactions</code>", style_td_mono),
            Paragraph("Rincian Pesanan per Item", style_td),
            Paragraph("Order ID, tanggal order, nilai bruto, potongan komisi, subsidi voucher, dan nilai bersih per transaksi.", style_td)
        ],
        [
            Paragraph("<code>stored_bank_rows</code>", style_td_mono),
            Paragraph("Mutasi Rekening Koran", style_td),
            Paragraph("Tanggal mutasi, deskripsi rekening, nominal kredit/debit, saldo berjalan, kode bank (BCA/Mandiri/BNI/BRI), dan referensi pencocokan.", style_td)
        ],
        [
            Paragraph("<code>stored_cod_settlements</code>", style_td_mono),
            Paragraph("Audit Trail Kurir COD", style_td),
            Paragraph("Nomor resi AWB, nama ekspedisi (JNE/SiCepat), Order ID, nilai COD, ongkos retensi, net remittance, dan status (MATCHED/SHORTAGE).", style_td)
        ],
        [
            Paragraph("<code>source_channels</code>", style_td_mono),
            Paragraph("Registry Saluran Data", style_td),
            Paragraph("Daftar kanal aktif, tipe kanal (BANK/MARKETPLACE/PG/POS/COD), dan strategi pencocokan yang diterapkan.", style_td)
        ],
        [
            Paragraph("<code>stored_discrepancies</code>", style_td_mono),
            Paragraph("Daftar Anomali & Selisih", style_td),
            Paragraph("Tipe selisih, tingkat keparahan (HIGH/MED/LOW), nominal kerugian, serta status penyelesaian klaim sengketa.", style_td)
        ]
    ]
    t_db = Table(db_tables, colWidths=[130, 135, 250])
    t_db.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY_MED),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_BG_ALT]),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(t_db)

    story.append(Paragraph("6.2 Mekanisme Rekonsiliasi Bergulir (Rolling Reconciliation)", style_h2))
    story.append(Paragraph(
        "Dana yang berstatus *In-Transit* pada periode lampau (akibat jeda kliring T+3) secara otomatis dipantau oleh sistem. Ketika rekening koran periode berikutnya diunggah:",
        style_body
    ))
    story.append(Paragraph("1. Sistem mendeteksi adanya mutasi kredit bank baru yang cocok dengan nomor referensi batch in-transit lampau.", style_bullet))
    story.append(Paragraph("2. Memanggil fungsi <code>mark_batch_resolved_rolling()</code> untuk melunasi status batch dari <code>TIMING_LAG</code> menjadi <code>RESOLVED_ROLLING</code>.", style_bullet))
    story.append(Paragraph("3. Memasukkan angka pelunasan in-transit tersebut ke formula Proof of Cash periode berjalan sehingga selisih kas tetap seimbang sempurna (**Rp 0.00**).", style_bullet))

    story.append(PageBreak())

    # =========================================================================
    # BAB 7: MANAJEMEN SENGKETA & INTEGRASI AKUNTANSI
    # =========================================================================
    story.append(Paragraph("Bab 7: Manajemen Sengketa & Integrasi Akuntansi", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("7.1 Generator Surat Klaim Sengketa Resmi (Dispute PDF)", style_h2))
    story.append(Paragraph(
        "Untuk setiap temuan anomali berstatus tinggi (*HIGH*) seperti *Missing Payout* atau *COD Shortage*, ReconAuto.ID menyediakan modul <code>core/dispute.py</code> yang menghasilkan berkas klaim formal dalam 1 klik:",
        style_body
    ))
    story.append(Paragraph("• <b>Format PDF Resmi Berkualitas Cetak:</b> Dilengkapi kop surat resmi perusahaan, nomor referensi surat otomatis, tanggal audit, rincian hukum wanprestasi, tabel daftar Order ID / AWB yang bermasalah, serta kolom tanda tangan pimpinan Finance & Accounting.", style_bullet))
    story.append(Paragraph("• <b>Draf Email Otomatis:</b> Menyusun draf pesan email lengkap dengan judul permohonan klaim dan rincian lampiran yang siap dikirimkan ke tim Merchant Care marketplace atau PIC ekspedisi kurir.", style_bullet))

    story.append(Paragraph("7.2 Ekspor Workbook Audit Excel Multi-Tab (.xlsx)", style_h2))
    story.append(Paragraph(
        "Melalui modul <code>core/exporter.py</code>, sistem mengekspor berkas Excel berstandar audit eksternal (*Big Four Audit Ready*) dengan 5 lembar kerja terstruktur:",
        style_body
    ))
    story.append(Paragraph("1. <b>Lembar Ringkasan Eksekutif:</b> Indikator KPI finansial, tingkat pencocokan (*Match Rate*), dan status Proof of Cash.", style_bullet))
    story.append(Paragraph("2. <b>Lembar Pembuktian Kas:</b> Rincian formula Proof of Cash baris demi baris beserta saldo awal dan akhir.", style_bullet))
    story.append(Paragraph("3. <b>Lembar Rincian Batch Settlement:</b> Seluruh batch TikTok, Shopee, DOKU, dan kasir lengkap dengan status kliring.", style_bullet))
    story.append(Paragraph("4. <b>Lembar Audit Rekening Koran:</b> Seluruh baris kredit/debit mutasi bank beserta referensi pencocokannya.", style_bullet))
    story.append(Paragraph("5. <b>Lembar Log Sengketa & Selisih:</b> Rincian lengkap anomali untuk tindak lanjut klaim pengembalian dana.", style_bullet))

    story.append(Paragraph("7.3 Draf Jurnal Penyesuaian GL & Integrasi API Akuntansi", style_h2))
    story.append(Paragraph(
        "Sistem secara otomatis mengonstruksi draf jurnal akuntansi berpasangan (*Double-Entry Bookkeeping*) sesuai bagan akun standar (COA):",
        style_body
    ))
    story.append(Paragraph("• <b>Debit Bank (1-1001) / Kredit Piutang Marketplace (1-1020/1-1021):</b> Untuk pencairan batch bersih.", style_bullet))
    story.append(Paragraph("• <b>Debit Beban Komisi Platform (6-2001) / Kredit Piutang Marketplace:</b> Pengakuan biaya layanan.", style_bullet))
    story.append(Paragraph("• <b>Debit Beban Selisih Kas (6-9001):</b> Pengakuan kekurangan fisik uang kasir atau kerugian shortage kurir.", style_bullet))
    story.append(Paragraph("• Mendukung ekspor format CSV siap impor serta modul sinkronisasi API ke <b>Mekari Jurnal</b>, <b>Accurate Online</b>, dan <b>SAP Business One</b>.", style_bullet))

    story.append(PageBreak())

    # =========================================================================
    # BAB 8: SPESIFIKASI REST API & LAPORAN HASIL PENGUJIAN (100% PASS)
    # =========================================================================
    story.append(Paragraph("Bab 8: Spesifikasi REST API & Hasil Uji (100% PASS)", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("8.1 Katalog Spesifikasi REST API (main.py)", style_h2))

    api_data = [
        [Paragraph("Metode & Jalur Endpoint", style_th), Paragraph("Deskripsi Fungsi", style_th), Paragraph("Struktur Parameter / Payload", style_th)],
        [
            Paragraph("<code>POST /api/reconcile</code>", style_td_mono),
            Paragraph("Menjalankan rekonsiliasi berkas multi-sumber.", style_td),
            Paragraph("Multipart form-data: <code>bank</code>, <code>marketplace</code>, <code>pg</code>, <code>pos</code>, <code>cod</code>", style_td)
        ],
        [
            Paragraph("<code>GET /api/demo</code>", style_td_mono),
            Paragraph("Memproses otomatis dataset demo 8 berkas.", style_td),
            Paragraph("Tanpa parameter (memuat sampel BCA, Mandiri, TikTok, Shopee, DOKU, POS, JNE, SiCepat)", style_td)
        ],
        [
            Paragraph("<code>GET /api/sources</code>", style_td_mono),
            Paragraph("Mengambil daftar saluran parser aktif di sistem.", style_td),
            Paragraph("Response JSON: daftar 11 saluran parser beserta strategi pencocokannya", style_td)
        ],
        [
            Paragraph("<code>POST /api/chat</code>", style_td_mono),
            Paragraph("Memproses percakapan interaktif ReconBot AI.", style_td),
            Paragraph("JSON: <code>{ message: string, history: list }</code><br/>Mengembalikan jawaban Gemini & eskalasi CS", style_td)
        ],
        [
            Paragraph("<code>GET /api/chat/cs-info</code>", style_td_mono),
            Paragraph("Mengambil nomor & tautan resmi WhatsApp CS.", style_td),
            Paragraph("Response JSON: nomor WhatsApp, email support, jam kerja", style_td)
        ],
        [
            Paragraph("<code>GET /api/history</code>", style_td_mono),
            Paragraph("Mendapatkan seluruh riwayat sesi audit SQLite.", style_td),
            Paragraph("Response JSON: daftar sesi, ringkasan in-transit, & dana terselesaikan", style_td)
        ],
        [
            Paragraph("<code>GET /api/history/{run_id}</code>", style_td_mono),
            Paragraph("Memuat ulang data sesi lampau ke dashboard.", style_td),
            Paragraph("Parameter URL: <code>run_id</code> (misal: <code>RUN-20260910-...</code>)", style_td)
        ],
        [
            Paragraph("<code>GET /api/export/excel</code>", style_td_mono),
            Paragraph("Mengunduh workbook audit Excel lengkap.", style_td),
            Paragraph("Response: Streaming berkas biner <code>.xlsx</code> (5 Sheet)", style_td)
        ]
    ]
    t_api = Table(api_data, colWidths=[140, 175, 200])
    t_api.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY_MED),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_BG_ALT]),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(t_api)

    story.append(Spacer(1, 8))
    story.append(Paragraph("8.2 Laporan Hasil Pengujian Otomatis (Semua Suite 100% Lulus)", style_h2))

    test_results = [
        [Paragraph("Rangkaian Pengujian (Test Suite)", style_th), Paragraph("Cakupan Fitur yang Diverifikasi", style_th), Paragraph("Tingkat Kelulusan", style_th)],
        [
            Paragraph("<b>test_phase1.py</b>", style_td),
            Paragraph("Parsing PDF/CSV BCA, uji rekonsiliasi dua arah, pembuktian kas matematis, dan generator klaim sengketa awal.", style_td),
            Paragraph("<b>100% PASS</b> (Selisih Rp 0.00)", style_td)
        ],
        [
            Paragraph("<b>test_phase2.py</b>", style_td),
            Paragraph("Persistensi SQLite rekonsile.db, pelacakan in-transit, penelusuran riwayat sesi, dan rekonsiliasi bergulir.", style_td),
            Paragraph("<b>100% PASS</b> (50 Sesi Tersimpan)", style_td)
        ],
        [
            Paragraph("<b>test_multi_bank.py</b>", style_td),
            Paragraph("Parser rekening koran Bank Mandiri (Kopra), BNI Direct, BRI CMS, SWIFT MT940, dan Bank BCA.", style_td),
            Paragraph("<b>100% PASS</b> (5 Format Bank Klop)", style_td)
        ],
        [
            Paragraph("<b>test_cod_reconciliation.py</b>", style_td),
            Paragraph("Audit 3-arah COD, deteksi COD_UNREMITTED & COD_SHORTAGE, integrasi AWB JNE & SiCepat ke kredit bank.", style_td),
            Paragraph("<b>100% PASS</b> (Variance Rp 0.00)", style_td)
        ],
        [
            Paragraph("<b>test_chatbot.py</b>", style_td),
            Paragraph("Integrasi Google Gemini AI, basis pengetahuan website, respons pertanyaan umum, dan deteksi eskalasi WhatsApp CS.", style_td),
            Paragraph("<b>100% PASS</b> (HTTP 200 OK)", style_td)
        ],
        [
            Paragraph("<b>test_cleanup.py</b>", style_td),
            Paragraph("Pembersihan kode mentah markdown/LaTeX ($$, \\text{}, ###) dan pembaruan badge versi resmi v1.0.0.", style_td),
            Paragraph("<b>100% PASS</b> (Format Bersih & Rapi)", style_td)
        ]
    ]
    t_test = Table(test_results, colWidths=[140, 265, 110])
    t_test.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_EMERALD),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_BG_ALT]),
        ('PADDING', (0, 0), (-1, -1), 4.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(t_test)

    story.append(PageBreak())

    # =========================================================================
    # BAB 9: PANDUAN OPERASIONAL STANDAR (SOP) PENGGUNA
    # =========================================================================
    story.append(Paragraph("Bab 9: Panduan Operasional Standar (SOP) Pengguna", style_h1))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BLUE_MAIN, spaceAfter=8))

    story.append(Paragraph("9.1 Prosedur Rekonsiliasi Rutin (Langkah demi Langkah)", style_h2))

    sop_steps = [
        [Paragraph("No", style_th), Paragraph("Tahapan Operasional", style_th), Paragraph("Tindakan Pengguna di Antarmuka Web (v1.0.0)", style_th)],
        [
            Paragraph("1", style_td),
            Paragraph("<b>Akses Aplikasi Web</b>", style_td),
            Paragraph("Buka browser Google Chrome atau Edge dan akses alamat <code>http://127.0.0.1:8000</code>.", style_td)
        ],
        [
            Paragraph("2", style_td),
            Paragraph("<b>Uji Coba Cepat (Demo 1-Klik)</b>", style_td),
            Paragraph("Klik tombol biru <b>⚡ Demo 1-Klik Multi-Sumber</b> di navbar atas. Sistem akan memuat konsolidasi seluruh 8 berkas sampel dan menampilkan hasil audit dalam 2 detik.", style_td)
        ],
        [
            Paragraph("3", style_td),
            Paragraph("<b>Unggah Berkas Mandiri</b>", style_td),
            Paragraph("Untuk data riil bulanan, unggah berkas pada 5 dropzone yang tersedia:<br/>"
                      "• Zona 1: Mutasi Bank (BCA, Mandiri, BNI, BRI, MT940)<br/>"
                      "• Zona 2: Marketplace Seller (TikTok Shop / Shopee)<br/>"
                      "• Zona 3: Payment Gateway (DOKU)<br/>"
                      "• Zona 4: Kasir POS Retail Tunai<br/>"
                      "• Zona 5: Ekspedisi COD Kurir (JNE / SiCepat)<br/>"
                      "Lalu klik tombol biru <b>Proses Rekonsiliasi Otomatis</b>.", style_td)
        ],
        [
            Paragraph("4", style_td),
            Paragraph("<b>Verifikasi Proof of Cash</b>", style_td),
            Paragraph("Periksa banner <b>Audit & Rekonsiliasi Kas Seimbang</b> di bagian atas. Pastikan formula kas menunjukkan <b>Tied Rp 0.00 (Klop 100%)</b> dan pelajari rincian selisih operasional yang berhasil diisolasi sistem.", style_td)
        ],
        [
            Paragraph("5", style_td),
            Paragraph("<b>Audit Tab COD Ekspedisi</b>", style_td),
            Paragraph("Buka tab ke-7 <b>Audit COD Ekspedisi (3-Way)</b> untuk meninjau status pencairan resi AWB kurir. Periksa apakah terdapat status <code>COD_UNREMITTED</code> (dana tertahan) atau <code>COD_SHORTAGE</code> (kurang setor).", style_td)
        ],
        [
            Paragraph("6", style_td),
            Paragraph("<b>Penerbitan Surat Sengketa</b>", style_td),
            Paragraph("Pada baris anomali bermasalah, klik tombol <b>Analisis & Klaim Dispute</b> lalu klik <b>Unduh Surat Klaim Resmi (PDF)</b> untuk langsung mencetak berkas klaim formal bertanda tangan.", style_td)
        ],
        [
            Paragraph("7", style_td),
            Paragraph("<b>Konsultasi via ReconBot AI / CS</b>", style_td),
            Paragraph("Klik tombol mengambang di pojok kanan bawah jika ada pertanyaan. Gunakan tombol <b>CS WhatsApp</b> di header chat untuk terhubung langsung ke WhatsApp Customer Support (+62 815-3617-5933).", style_td)
        ],
        [
            Paragraph("8", style_td),
            Paragraph("<b>Ekspor Laporan & Tutup Buku</b>", style_td),
            Paragraph("Klik tombol <b>Unduh Excel (5 Tab)</b> untuk arsip bukti audit eksternal dan klik <b>Export Jurnal CSV</b> untuk sinkronisasi ke software akuntansi perusahaan.", style_td)
        ]
    ]
    t_sop = Table(sop_steps, colWidths=[25, 135, 355])
    t_sop.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_NAVY_MED),
        ('GRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_BG_ALT]),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(t_sop)

    story.append(Spacer(1, 10))
    story.append(Paragraph("9.2 Prosedur Pemeliharaan & Pencadangan Basis Data", style_h2))
    story.append(Paragraph(
        "Seluruh data transaksi dan histori audit disimpan secara terpusat pada berkas lokal <code>rekonsile.db</code> di direktori root aplikasi. Lakukan penyalinan (*copy backup*) berkas tersebut ke media penyimpanan terpisah setiap kali proses tutup buku bulanan selesai dilakukan.",
        style_body
    ))

    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=10))
    story.append(Paragraph(
        "<font color='#64748B'><b>Pengesahan Dokumen Resmi:</b><br/>"
        "Disusun oleh: Tim Rekayasa Perangkat Lunak & Finansial ReconAuto.ID &nbsp;|&nbsp; Ditinjau oleh: Lead Financial Auditor & CTO<br/>"
        "Status: Dokumen Resmi Terverifikasi &nbsp;|&nbsp; Versi Sistem: v1.0.0 &nbsp;|&nbsp; Tanggal Pengesahan: September 2026</font>",
        ParagraphStyle('FooterSign', fontName='Helvetica', fontSize=8, leading=11, alignment=1)
    ))

    # Bangun PDF Dokumen
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] PDF Berhasil Dibuat: {pdf_path}")
    print(f"[INFO] Ukuran File: {os.path.getsize(pdf_path):,} bytes")
    return pdf_path

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "Dokumentasi_Lengkap_ReconAuto_ID.pdf"
    build_pdf(out_file)
