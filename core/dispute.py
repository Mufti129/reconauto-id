"""
core/dispute.py
---------------
Modul pembuat dokumen klaim dispute otomatis (Auto-Dispute Claim Generator)
untuk kasus Missing Payout, Fee Overcharge, dan Cash Shortage.
Menghasilkan draf email resmi dan dokumen PDF bertanda tangan.
"""

import io
from datetime import datetime
from typing import Dict, Any, List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_dispute_data(discrepancy: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menyusun struktur data surat klaim berdasarkan anomali yang dipilih.
    """
    issue_type = discrepancy.get("issue_type", "")
    ref_id = discrepancy.get("reference_id", "")
    channel = discrepancy.get("channel", "Marketplace")
    amount = abs(discrepancy.get("discrepancy_amount", 0.0))
    date_str = discrepancy.get("date", datetime.now().strftime("%Y-%m-%d"))
    
    # Cari item pesanan yang terkait jika ini batch
    related_orders = []
    match_analytics = result.get("match_analytics", {})
    for cat in match_analytics.get("categories", []):
        for itm in cat.get("items", []):
            if itm.get("batch_id") == ref_id or itm.get("id") == ref_id:
                related_orders.append(itm)
                
    if not related_orders:
        # Fallback jika tidak ditemukan di kategori
        related_orders.append({
            "id": ref_id,
            "date": date_str,
            "channel": channel,
            "description": discrepancy.get("probable_cause", "Discrepancy Item"),
            "gross_amount": discrepancy.get("expected_amount", amount),
            "fee_amount": 0.0,
            "net_amount": amount,
            "batch_id": ref_id
        })

    today_str = datetime.now().strftime("%d %B %Y")
    
    if "MISSING" in issue_type:
        title = "SURAT KLAIM PENCAIRAN DANA BELUM DITERIMA (MISSING PAYOUT)"
        recipient = f"Tim Finance & Settlement {channel}"
        subject = f"[KLAIM DANA TERTARIK] Permohonan Investigasi Batch Payout {ref_id} - Total Rp {amount:,.0f}"
        summary_text = (
            f"Berdasarkan hasil rekonsiliasi keuangan dua arah (*two-way reconciliation*) antara laporan Seller Center "
            f"dan rekening koran Bank BCA kami, ditemukan bahwa penarikan dana nomor batch {ref_id} sebesar "
            f"Rp {amount:,.0f} yang tercatat 'Completed' pada tanggal {date_str} sampai saat ini BELUM PERNAH "
            f"diterima mutasi kreditnya di rekening bank operasional kami."
        )
        action_requested = (
            f"Mohon pihak Finance {channel} segera melakukan pengecekan status transfer bank / ARN (Acquirer Reference Number) "
            f"atau melakukan transfer ulang ke rekening terdaftar kami."
        )
    elif "FEE" in issue_type or "OVERCHARGE" in issue_type:
        title = "SURAT SANGGAHAN KELEBIHAN POTONGAN KOMISI (FEE OVERCHARGE)"
        recipient = f"Tim Merchant Support & Finance {channel}"
        subject = f"[DISPUTE FEE] Sanggahan Kelebihan Potongan Komisi Order {ref_id} - Selisih Rp {amount:,.0f}"
        summary_text = (
            f"Ditemukan ketidaksesuaian tarif komisi platform pada transaksi {ref_id}. Sesuai perjanjian kategori produk kami, "
            f"rate komisi standar adalah 5.0%. Namun pada laporan settlement tercatat potongan sebesar "
            f"Rp {discrepancy.get('actual_amount', 0):,.0f} ({discrepancy.get('metadata', {}).get('rate_applied', '9%')}), "
            f"sehingga terdapat kelebihan pemotongan dana seller sebesar Rp {amount:,.0f}."
        )
        action_requested = (
            f"Mohon dilakukan penyesuaian (*credit adjustment*) atau pengembalian selisih fee sebesar Rp {amount:,.0f} "
            f"ke saldo penjual pada periode settlement berikutnya."
        )
    else:
        title = "BERITA ACARA KLARIFIKASI SELISIH REKONSILIASI KAS"
        recipient = "Manajemen Operasional & Keuangan Toko"
        subject = f"[BERITA ACARA] Klarifikasi Selisih Finansial Ref {ref_id}"
        summary_text = (
            f"Tercatat selisih rekonsiliasi pada transaksi {ref_id} sebesar Rp {amount:,.0f}. "
            f"Penyebab teridentifikasi: {discrepancy.get('probable_cause', '-')}"
        )
        action_requested = "Mohon pihak terkait melakukan investigasi dan penyesuaian buku kas fisik."

    return {
        "letter_number": f"DISP/{datetime.now().strftime('%Y%m')}/{ref_id[:10]}",
        "date": today_str,
        "title": title,
        "recipient": recipient,
        "subject": subject,
        "channel": channel,
        "ref_id": ref_id,
        "amount": amount,
        "summary_text": summary_text,
        "action_requested": action_requested,
        "orders": related_orders,
        "bank_account": {
            "bank_name": "Bank Central Asia (BCA)",
            "account_number": "8820-192-881",
            "account_name": "PT REKON AUTO INDONESIA",
            "branch": "KCU Thamrin Jakarta"
        }
    }

def generate_dispute_email_text(data: Dict[str, Any]) -> str:
    """
    Menghasilkan teks draf email resmi siap salin.
    """
    text = f"""Kepada Yth.
{data['recipient']}

Perihal: {data['subject']}
No. Referensi: {data['letter_number']}
Tanggal: {data['date']}

Dengan hormat,

Melalui surat/email ini, kami dari bagian Finance Merchant mengajukan permohonan investigasi dan klaim atas ketidaksesuaian pencairan dana pada sistem kami.

RINGKASAN KASUS:
----------------------------------------------------------------------
• Jenis Masalah   : {data['title']}
• Kanal / Platform: {data['channel']}
• Nomor Batch/Ref : {data['ref_id']}
• Total Nominal   : Rp {data['amount']:,.2f}
----------------------------------------------------------------------

URAIAN TEMUAN:
{data['summary_text']}

RINCIAN PESANAN / TRANSAKSI TERKAIT:
"""
    for idx, o in enumerate(data.get("orders", []), 1):
        text += f"{idx}. Order ID: {o.get('id')} | Tanggal: {o.get('date')} | Gross: Rp {o.get('gross_amount', 0):,.0f} | Net Hak Seller: Rp {o.get('net_amount', 0):,.0f}\n"

    text += f"""
REKENING BANK PENERIMA YANG TERDAFTAR:
• Bank          : {data['bank_account']['bank_name']}
• Nomor Rekening: {data['bank_account']['account_number']}
• Atas Nama     : {data['bank_account']['account_name']}
• Kantor Cabang : {data['bank_account']['branch']}

TINDAKAN YANG DIMOHONKAN:
{data['action_requested']}

Kami telah melampirkan mutasi rekening koran bank BCA kami sebagai bukti tidak adanya dana masuk pada tanggal tersebut. Atas perhatian dan kerjasamanya, kami ucapkan terima kasih.

Hormat kami,
Finance & Reconciliation Dept.
ReconAuto.ID Platform
"""
    return text

def generate_dispute_pdf(data: Dict[str, Any]) -> io.BytesIO:
    """
    Menghasilkan dokumen PDF surat klaim resmi dengan kop surat, tabel, dan kotak verifikasi.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    
    h2_style = ParagraphStyle(
        'Heading2Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#1E3A8A')
    )
    
    normal_style = ParagraphStyle(
        'NormalCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1F2937')
    )
    
    bold_style = ParagraphStyle(
        'BoldCustom',
        parent=normal_style,
        fontName='Helvetica-Bold'
    )
    
    elements = []
    
    # 1. Header / Letterhead
    elements.append(Paragraph("<b>RECONAUTO MERCHANT SERVICES</b>", ParagraphStyle('Head', parent=title_style, fontSize=15, alignment=0, textColor=colors.HexColor('#2563EB'))))
    elements.append(Paragraph("Divisi Rekonsiliasi Finansial & Audit Transaksi Multi-Platform", normal_style))
    elements.append(Paragraph("Email: finance@reconauto.id | Telp: (021) 555-8921 | Gedung Bursa Efek Tower 2 Jakarta", normal_style))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1E3A8A'), spaceBefore=2, spaceAfter=12))
    
    # 2. Document Title
    elements.append(Paragraph(data['title'], title_style))
    elements.append(Paragraph(f"Nomor: {data['letter_number']} | Tanggal: {data['date']}", ParagraphStyle('Sub', parent=normal_style, alignment=1, textColor=colors.HexColor('#6B7280'))))
    elements.append(Spacer(1, 14))
    
    # 3. Recipient Info
    elements.append(Paragraph(f"<b>Kepada Yth:</b><br/>{data['recipient']}<br/>Platform: {data['channel']}", normal_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Perihal:</b> {data['subject']}", bold_style))
    elements.append(Spacer(1, 10))
    
    # 4. Summary Box
    summary_data = [
        [Paragraph("<b>Status Temuan:</b>", normal_style), Paragraph(f"<font color='#DC2626'><b>DISCREPANCY DETECTED</b></font>", normal_style)],
        [Paragraph("<b>Nomor Batch / Ref:</b>", normal_style), Paragraph(f"<b>{data['ref_id']}</b>", normal_style)],
        [Paragraph("<b>Total Nilai Klaim:</b>", normal_style), Paragraph(f"<b><font size='11' color='#B91C1C'>Rp {data['amount']:,.2f}</font></b>", normal_style)],
        [Paragraph("<b>Uraian Permasalahan:</b>", normal_style), Paragraph(data['summary_text'], normal_style)],
    ]
    t_sum = Table(summary_data, colWidths=[130, 410])
    t_sum.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_sum)
    elements.append(Spacer(1, 12))
    
    # 5. Table of Orders Involved
    elements.append(Paragraph("<b>Daftar Rincian Pesanan / Transaksi yang Diklaim:</b>", h2_style))
    elements.append(Spacer(1, 4))
    
    order_headers = [Paragraph("<b>No. Order / ID</b>", normal_style), Paragraph("<b>Tgl Transaksi</b>", normal_style), Paragraph("<b>Deskripsi / SKU</b>", normal_style), Paragraph("<b>Gross (Rp)</b>", normal_style), Paragraph("<b>Net Hak Seller (Rp)</b>", normal_style)]
    order_rows = [order_headers]
    for o in data.get("orders", []):
        order_rows.append([
            Paragraph(str(o.get('id')), normal_style),
            Paragraph(str(o.get('date')), normal_style),
            Paragraph(str(o.get('description'))[:30], normal_style),
            Paragraph(f"Rp {o.get('gross_amount', 0):,.0f}", normal_style),
            Paragraph(f"<b>Rp {o.get('net_amount', 0):,.0f}</b>", normal_style),
        ])
        
    t_orders = Table(order_rows, colWidths=[100, 75, 165, 95, 105])
    t_orders.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_orders)
    elements.append(Spacer(1, 12))
    
    # 6. Bank Account Table
    elements.append(Paragraph("<b>Konfirmasi Rekening Bank Resmi Tujuan Pencairan:</b>", h2_style))
    elements.append(Spacer(1, 4))
    bank_data = [
        [Paragraph("<b>Nama Bank:</b>", normal_style), Paragraph(data['bank_account']['bank_name'], normal_style)],
        [Paragraph("<b>Nomor Rekening:</b>", normal_style), Paragraph(f"<b>{data['bank_account']['account_number']}</b>", normal_style)],
        [Paragraph("<b>Nama Pemilik Rekening:</b>", normal_style), Paragraph(data['bank_account']['account_name'], normal_style)],
        [Paragraph("<b>Kantor Cabang:</b>", normal_style), Paragraph(data['bank_account']['branch'], normal_style)],
    ]
    t_bank = Table(bank_data, colWidths=[130, 410])
    t_bank.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDF4')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#86EFAC')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCFCE7')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_bank)
    elements.append(Spacer(1, 12))
    
    # 7. Action Requested & Signatures
    elements.append(Paragraph(f"<b>Permohonan Tindakan:</b> {data['action_requested']}", normal_style))
    elements.append(Spacer(1, 20))
    
    sig_data = [
        [Paragraph("Diajukan Oleh,<br/><br/><br/><br/><b><u>Budi Santoso, S.E.</u></b><br/>Lead Financial Reconciler", normal_style),
         Paragraph("Mengetahui & Menyetujui,<br/><br/><br/><br/><b><u>Hendra Pratama</u></b><br/>Finance Director / Merchant Owner", normal_style)]
    ]
    t_sig = Table(sig_data, colWidths=[270, 270])
    t_sig.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(t_sig)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
