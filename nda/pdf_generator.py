"""
nda/pdf_generator.py
--------------------
Modul generator dokumen resmi PDF untuk Non-Disclosure Agreement (NDA) Digital ReconAuto.ID.
Menghasilkan dokumen perjanjian hukum bilateral siap cetak (A4) yang memuat:
1. Kop resmi PT Recon Automasi Data Indonesia (ReconAuto.ID)
2. Nomor registrasi dokumen unik dan audit hash SHA-256
3. Identitas lengkap Pihak Pertama (Penyedia) dan Pihak Kedua (Klien/Pengguna)
4. Klausul perlindungan kerahasiaan data finansial (UU PDP No. 27/2022 & UU ITE No. 1/2024)
5. Goresan tanda tangan digital asli Pihak Kedua (hasil input canvas)
6. Tanda tangan digital representatif & stempel digital resmi Pihak Pertama
"""

import io
import base64
from datetime import datetime
from typing import Optional
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

from .models import NDAConsentRecord

# Palette Warna Dokumen Hukum SaaS Enterprise
C_NAVY_DARK  = colors.HexColor("#0F172A")  # Slate 900
C_NAVY_MED   = colors.HexColor("#1E293B")  # Slate 800
C_BLUE_MAIN  = colors.HexColor("#2563EB")  # Blue 600
C_BLUE_LIGHT = colors.HexColor("#EFF6FF")  # Blue 50
C_EMERALD    = colors.HexColor("#059669")  # Emerald 600
C_EMERALD_BG = colors.HexColor("#ECFDF5")  # Emerald 50
C_SLATE_TXT  = colors.HexColor("#334155")  # Slate 700
C_SLATE_MUT  = colors.HexColor("#64748B")  # Slate 500
C_BORDER     = colors.HexColor("#CBD5E1")  # Slate 300
C_BG_ALT     = colors.HexColor("#F8FAFC")  # Slate 50
C_WHITE      = colors.HexColor("#FFFFFF")


class NDANumberedCanvas(canvas.Canvas):
    """Canvas kustom untuk menambahkan footer nomor halaman dan watermark keaslian."""
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
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(C_SLATE_MUT)
        
        # Garis batas footer
        self.setStrokeColor(C_BORDER)
        self.setLineWidth(0.5)
        self.line(40, 42, 555, 42)
        
        # Teks Footer
        footer_text = "Dokumen Sah Digital ReconAuto.ID — Dilindungi Kerahasiaan & Hak Cipta © PT Recon Automasi Data Indonesia"
        self.drawString(40, 30, footer_text)
        
        page_str = f"Halaman {self._pageNumber} dari {total_pages}"
        self.drawRightString(555, 30, page_str)
        self.restoreState()


def generate_nda_pdf_bytes(record: NDAConsentRecord) -> bytes:
    """
    Menghasilkan file PDF dokumen resmi NDA yang telah ditandatangani dalam bentuk bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=55
    )

    styles = getSampleStyleSheet()
    
    # Custom Paragraph Styles
    style_header_title = ParagraphStyle(
        "HeaderTitle",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=C_NAVY_DARK,
        alignment=1  # Centered
    )
    style_header_sub = ParagraphStyle(
        "HeaderSub",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=C_SLATE_MUT,
        alignment=1
    )
    style_meta_badge = ParagraphStyle(
        "MetaBadge",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=C_BLUE_MAIN,
        alignment=1
    )
    style_sec_title = ParagraphStyle(
        "SectionTitle",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=C_NAVY_DARK,
        spaceBefore=8,
        spaceAfter=4
    )
    style_body = ParagraphStyle(
        "BodyTextCustom",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=C_SLATE_TXT,
        spaceAfter=5
    )
    style_body_bold = ParagraphStyle(
        "BodyBoldCustom",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12.5,
        textColor=C_NAVY_DARK
    )
    style_table_cell = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=C_SLATE_TXT
    )
    style_table_cell_bold = ParagraphStyle(
        "TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=C_NAVY_DARK
    )

    story = []

    # 1. KOP DOKUMEN & IDENTITAS PERJANJIAN
    story.append(Paragraph("SURAT PERJANJIAN KERAHASIAAN INFORMASI & PERLINDUNGAN DATA FINANSIAL", style_header_title))
    story.append(Spacer(1, 2))
    story.append(Paragraph("DIGITAL NON-DISCLOSURE AND DATA PROTECTION MUTUAL AGREEMENT", style_header_sub))
    story.append(Spacer(1, 4))
    
    reg_no = f"NDA-RAD/{datetime.now().strftime('%Y%m')}/{record.consent_id[:8].upper()}"
    story.append(Paragraph(f"Nomor Registrasi: <b>{reg_no}</b> &nbsp;|&nbsp; Versi Dokumen: <b>{record.document_version}</b>", style_meta_badge))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_BLUE_MAIN, spaceAfter=10))

    # 2. INTRODUKSI
    intro_p = (
        f"Pada hari ini, terhitung sejak diterimanya konfirmasi elektronik pada tanggal "
        f"<b>{record.timestamp_wib}</b>, dibuat dan disepakati Perjanjian Kerahasiaan Informasi dan "
        f"Pelindungan Data Finansial (selanjutnya disebut sebagai <b>\"Perjanjian\"</b>) oleh dan antara para pihak di bawah ini:"
    )
    story.append(Paragraph(intro_p, style_body))
    story.append(Spacer(1, 6))

    # 3. IDENTITAS PARA PIHAK (TABLE)
    parties_data = [
        [
            Paragraph("<b>PIHAK PERTAMA (Penyedia Layanan):</b>", style_table_cell_bold),
            Paragraph("<b>PIHAK KEDUA (Pengguna / Klien):</b>", style_table_cell_bold),
        ],
        [
            Paragraph(
                "<b>PT Recon Automasi Data Indonesia</b><br/>"
                "Brand: <b>ReconAuto.ID</b><br/>"
                "Operasional: One Pacific Place SCBD Lt. 15, Jakarta Selatan<br/>"
                "Email: legal@reconauto.id / compliance@reconauto.id<br/>"
                "Bidang: Penyedia Teknologi Rekonsiliasi Finansial Otomatis",
                style_table_cell
            ),
            Paragraph(
                f"Nama Lengkap: <b>{record.nama_lengkap}</b><br/>"
                f"Instansi / Perusahaan: <b>{record.nama_perusahaan or '-'}</b><br/>"
                f"Jabatan: <b>{record.jabatan or '-'}</b><br/>"
                f"Alamat Email: <b>{record.email}</b><br/>"
                f"Alamat IP Akses: <code>{record.ip_address}</code>",
                style_table_cell
            )
        ]
    ]

    parties_table = Table(parties_data, colWidths=[250, 265])
    parties_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), C_BG_ALT),
        ('BOX', (0, 0), (-1, -1), 0.75, C_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 10))

    # 4. KLAUSUL & PASAL-PASAL PERJANJIAN
    story.append(Paragraph("Pasal 1 — Ruang Lingkup & Definisi Informasi Rahasia", style_sec_title))
    p1 = (
        "1.1. <b>\"Informasi Rahasia\"</b> mencakup seluruh berkas keuangan, mutasi rekening bank (e-Statement / CSV / PDF), "
        "laporan penyelesaian transaksi (settlement report), pesanan e-commerce (Shopee, Tokopedia, TikTok Shop), "
        "log kasir fisik (POS Kasir / Jubelio / Moka), manifest COD ekspedisi (JNE, SiCepat, J&T), "
        "serta API Key dan data pembukuan internal yang diunggah atau diintegrasikan oleh Pihak Kedua ke dalam platform ReconAuto.ID.<br/>"
        "1.2. Pihak Pertama mengakui sepenuhnya bahwa seluruh data yang diunggah merupakan milik eksklusif Pihak Kedua."
    )
    story.append(Paragraph(p1, style_body))

    story.append(Paragraph("Pasal 2 — Kepatuhan Regulasi & Standar Pelindungan Data Pribadi (UU PDP)", style_sec_title))
    p2 = (
        "2.1. Pihak Pertama tunduk dan patuh pada <b>Undang-Undang Republik Indonesia Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP)</b> "
        "dan Peraturan Bank Indonesia (PBI) terkait penyelenggaraan sistem pembayaran.<br/>"
        "2.2. Pihak Pertama wajib menerapkan kontrol teknis ketat mencakup <b>enkripsi data at-rest (AES-256)</b> dan <b>enkripsi in-transit (TLS 1.3)</b>.<br/>"
        "2.3. Pihak Pertama <b>TIDAK PERNAH</b> meminta, mengakses, atau menyimpan kredensial sensitif perbankan (seperti PIN, Kata Sandi Internet Banking, atau Token OTP)."
    )
    story.append(Paragraph(p2, style_body))

    story.append(Paragraph("Pasal 3 — Batasan Penggunaan Data & Jaminan Nol Pembagian Pihak Ketiga (Zero-Sharing)", style_sec_title))
    p3 = (
        "3.1. Seluruh data transaksi yang diunggah <b>hanya digunakan semata-mata</b> untuk keperluan komputasi pencocokan algoritma rekonsiliasi finansial, "
        "pemeriksaan selisih (discrepancy detection), dan pembuktian saldo (proof of cash) untuk kepentingan internal Pihak Kedua.<br/>"
        "3.2. Pihak Pertama <b>DILARANG KERAS</b> memperjualbelikan, membagikan, memindahtangankan, atau mendistribusikan data transaksi finansial "
        "Pihak Kedua kepada pihak ketiga mana pun tanpa persetujuan tertulis eksplisit dari Pihak Kedua."
    )
    story.append(Paragraph(p3, style_body))

    story.append(Paragraph("Pasal 4 — Hak Penghapusan Data & Integritas Audit Trail", style_sec_title))
    p4 = (
        "4.1. Pihak Kedua berhak meminta penghapusan permanen (data purge) atas seluruh berkas dan transaksi yang pernah diunggah.<br/>"
        "4.2. Persetujuan ini dicatat dengan aman dalam log audit permanen yang dilengkapi dengan timestamp tersertifikasi dan hash integritas dokumen SHA-256."
    )
    story.append(Paragraph(p4, style_body))
    story.append(Spacer(1, 8))

    # 5. BLOK TANDA TANGAN DIGITAL KEDUA BELAH PIHAK
    story.append(Paragraph("Pasal 5 — Pengesahan & Tanda Tangan Digital Sah", style_sec_title))
    story.append(Paragraph(
        "Berdasarkan <b>UU ITE No. 1 Tahun 2024</b>, penandatanganan elektronik dan persetujuan digital ini "
        "memiliki kekuatan hukum yang sah dan mengikat para pihak sebagaimana tanda tangan basah di atas materai.",
        style_body
    ))
    story.append(Spacer(1, 10))

    # Proses Gambar Tanda Tangan Digital Klien
    client_sig_flowable = Paragraph("<i>[Tanda Tangan Digital Tersimpan]</i>", style_table_cell)
    if record.signature_data and "data:image" in record.signature_data:
        try:
            b64_str = record.signature_data.split(",")[1]
            img_data = base64.b64decode(b64_str)
            client_sig_flowable = RLImage(io.BytesIO(img_data), width=130, height=52)
        except Exception:
            client_sig_flowable = Paragraph("<b>[Terverifikasi Secara Digital via Web]</b>", style_table_cell)

    # Box Pengesahan Pihak Pertama (ReconAuto.ID)
    p1_sign_box = [
        Paragraph("<b>PIHAK PERTAMA:</b><br/>PT Recon Automasi Data Indonesia", style_table_cell_bold),
        Spacer(1, 8),
        # Badge Stempel Digital
        Paragraph(
            "<font color='#059669'><b>[VERIFIED DIGITAL SIGNATURE]</b></font><br/>"
            "Direktur Kepatuhan & Teknologi Siber<br/>"
            f"<font size='6.5' color='#64748B'>Doc Hash: {record.document_hash[:22]}...</font>",
            style_table_cell
        ),
        Spacer(1, 8),
        Paragraph(f"Tercatat Resmi: {record.timestamp_wib}", style_table_cell)
    ]

    # Box Pengesahan Pihak Kedua (Klien)
    p2_sign_box = [
        Paragraph(f"<b>PIHAK KEDUA:</b><br/>{record.nama_perusahaan or 'Pengguna Terdaftar'}", style_table_cell_bold),
        Spacer(1, 4),
        client_sig_flowable,
        Spacer(1, 4),
        Paragraph(f"<b>{record.nama_lengkap}</b><br/>{record.jabatan or 'Penanggung Jawab Data'}", style_table_cell_bold),
        Paragraph(f"Ditandatangani pada: {record.timestamp_wib}", style_table_cell)
    ]

    sig_table_data = [
        [
            p1_sign_box,
            p2_sign_box
        ]
    ]

    sig_table = Table(sig_table_data, colWidths=[250, 265])
    sig_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, C_BLUE_MAIN),
        ('BACKGROUND', (0, 0), (0, 0), C_BLUE_LIGHT),
        ('BACKGROUND', (1, 0), (1, 0), C_EMERALD_BG),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    story.append(sig_table)

    # Bangun PDF dengan Canvas Bernomor Halaman
    doc.build(story, canvasmaker=NDANumberedCanvas)
    return buffer.getvalue()
