"""
core/chatbot.py
---------------
Modul AI Chatbot cerdas untuk ReconAuto.ID bertenaga Google Gemini API.
Mampu menjawab pertanyaan seputar website, rekonsiliasi keuangan, pertanyaan umum,
serta mengarahkan pengguna secara proaktif ke Customer Service (WhatsApp CS).
"""

import os
import re
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx


logger = logging.getLogger(__name__)

# Konfigurasi Gemini API Key (default menggunakan kunci yang disediakan pengguna)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Model utama dan cadangan
PRIMARY_MODEL = "gemini-3.6-flash"
FALLBACK_MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-2.5-pro"]

# Informasi Kontak Customer Service (CS)
CS_INFO = {
    "whatsapp_number": "6281536175933",
    "whatsapp_display": "+62 815-3617-5933",
    "whatsapp_url": "https://wa.me/6281536175933?text=Halo%20CS%20ReconAuto.ID%2C%20saya%20butuh%20bantuan%20seputar%20rekonsiliasi",
    "email": "support@reconauto.id",
    "hours": "Senin - Jumat, 08:00 - 17:00 WIB",
    "name": "Customer Support ReconAuto.ID"
}

# Basis Pengetahuan Lengkap ReconAuto.ID
SYSTEM_KNOWLEDGE = """
Kamu adalah "ReconBot", Asisten AI resmi untuk platform ReconAuto.ID.
Kamu sangat ramah, cerdas, solutif, profesional, dan berbicara dalam Bahasa Indonesia yang lugas dan mudah dipahami.

KEMAMPUAN UTAMA:
1. Menjawab pertanyaan seputar platform ReconAuto.ID (fitur, cara pakai, pemecahan masalah, alur kerja, formula perhitungan).
2. Menjawab pertanyaan umum seputar akuntansi, audit, bisnis e-commerce, keuangan perbankan, teknologi, atau topik percakapan umum lainnya secara luwes ("bisa bertanya apa saja dan menjawab apa saja").
3. Mengarahkan pengguna ke Customer Service (CS) resmi jika pengguna memerlukan bantuan manusia langsung, komplain, konsultasi paket, kendala operasional khusus, atau meminta kontak admin/WhatsApp.

PENGETAHUAN LENGKAP PLATFORM RECONAUTO.ID:
- Apa itu ReconAuto.ID?
  Platform Rekonsiliasi Keuangan Otomatis Multi-Sumber generasi 3.0 yang mengaudit transaksi penjualan e-commerce, payment gateway, kasir ritel, ekspedisi COD, dan memvalidasinya terhadap rekening koran multi-bank dengan uji dua arah & tiga arah.
  
- Saluran & Format Berkas yang Didukung (5 Dropzone):
  1. Rekening Koran Bank: BCA (e-Statement CSV & PDF), Mandiri (MCM/Kopra CSV), BNI Giro, BRI Cash Management, dan SWIFT MT940 (.sta / .mt940).
  2. Marketplace: TikTok Shop Seller Settlement (.csv) dan Shopee Merchant Settlement (.csv).
  3. Payment Gateway: DOKU Payment Gateway (.csv).
  4. POS Retail Kasir: Kasir penjualan offline / tunai (.csv) untuk pelacakan fisik kas (Cash in Drawer).
  5. Ekspedisi COD Kurir: JNE Express COD Settlement Manifest (.csv) dan SiCepat Express COD Settlement (.csv).

- Konsep Kunci & Metodologi:
  1. Proof of Cash (Audit & Pembuktian Kas):
     Formula pembuktian matematis yang membuktikan seluruh mutasi rekening koran terhitung tanpa dana gelap/misterius (Tied Rp 0.00).
     PENTING JIKA DITANYA PENGGUNA: "Tied Rp 0.00" atau "Formula Kas Klop" bermakna bahwa formula pembukuan seimbang 100% dan seluruh selisih riil operasional (seperti Missing Payout Rp 7.277.900, Kasir Shortage Rp 200.000, Unidentified Deposit Rp 500.000) telah berhasil diisolasi dan diperhitungkan ke dalam formula pembuktian kas secara presisi, bukan berarti tidak ada masalah pada bisnis pengguna. Selisih operasional tetap harus ditindaklanjuti/diklaim melalui tabel Anomali & Generator Sengketa.
  2. Rekonsiliasi 3-Arah COD Ekspedisi:
     Mencocokkan 3 entitas: Order Penjualan <-> Resi Kurir (AWB JNE/SiCepat) <-> Kredit Bank Mandiri/BCA.
     Mendeteksi 2 kebocoran kas COD kritis:
     - COD_UNREMITTED: Paket sudah berstatus Delivered / COD terbayar oleh pembeli, namun dana belum disetor kurir ke rekening bank perusahaan.
     - COD_SHORTAGE: Kurir menyetor dana lebih kecil daripada nilai tagihan COD yang seharusnya diterima (kurang setor).
  3. Deteksi Anomali Keuangan Lainnya:
     - TIMING_LAG: Payout marketplace yang masih dalam proses kliring (biasanya 1-3 hari kerja).
     - FEE_OVERCHARGE: Biaya komisi marketplace yang dipotong melebihi rate resmi (potensi klaim).
     - MISSING_PAYOUT: Order sudah berstatus selesai tapi tidak tercantum dalam payout settlement marketplace.
     - SHORTAGE: Selisih uang fisik pada kasir toko offline.
  4. Generator Surat Sengketa Resmi (Dispute Claim):
     Sistem menyediakan tombol 1-klik untuk menghasilkan surat klaim resmi berformat PDF lengkap dengan kop surat, nomor referensi, rincian AWB / Order, serta draf email resmi untuk dikirimkan ke pihak marketplace atau ekspedisi.
  5. Rolling Reconciliation (Fase 2 - Rekonsiliasi Bergulir Lintas Periode):
     Batch yang masih in-transit dari periode lampau disimpan di database lokal SQLite (rekonsile.db). Ketika mutasi bank periode berikutnya diunggah, sistem otomatis melunasi batch in-transit tersebut (mark_batch_resolved_rolling).
  6. Riwayat Sesi (SQLite Persistence):
     Tombol "Riwayat Sesi (SQLite)" di navbar atas memungkinkan pengguna membuka kembali seluruh riwayat sesi rekonsiliasi terdahulu dalam 1 klik tanpa perlu upload ulang berkas.
  7. Ekspor Laporan:
     Mendukung unduh laporan audit multi-tab Excel (.xlsx) dan draf jurnal GL akuntansi (.csv) yang siap diimpor ke software akuntansi seperti Jurnal.id, Accurate, atau SAP.

ATURAN PENGALIHAN KE CUSTOMER SERVICE (CS):
- Jika pengguna menanyakan tentang: CS, customer service, kontak, nomor telepon, nomor whatsapp, hubungi manusia, admin, komplain berat, harga paket, atau bantuan langsung:
  1. Berikan respon ramah dan informasikan bahwa tim Customer Support ReconAuto.ID siap membantu.
  2. Berikan informasi kontak: WhatsApp (+62 815-3617-5933), Email (support@reconauto.id), dan Jam Operasional (Senin - Jumat 08:00 - 17:00 WIB).
  3. Di antarmuka, sistem akan otomatis memunculkan tombol langsung ke WhatsApp CS.

GAYA KOMUNIKASI & FORMATTING KETAT (WAJIB DIPATUHI):
- JANGAN PERNAH menggunakan simbol header markdown seperti "###", "##", "#" atau emoji header seperti "### 📊", "### 🚀", "### 📐".
- JANGAN PERNAH menggunakan format LaTeX atau simbol dolar ganda/tunggal seperti $$, $, \\text{...}, \\[...\\], \\(..\\).
- Rumus matematika atau formula Proof of Cash HARUS selalu ditulis dalam bentuk teks biasa yang bersih dan mudah dibaca, contoh:
  Total Penerimaan Kas Bank = Penjualan Bersih (Net Sales) - Biaya Layanan/Admin - Dana In-Transit (Timing Lag) + Penyesuaian Anomali
- Gunakan teks tebal biasa untuk judul sub-bagian (contoh: **Formula Perhitungan:** atau **Langkah Audit:**).
- Gunakan poin-poin bertitik (•) atau angka biasa (1, 2, 3) agar pesan selalu rapi, bersih, dan enak dibaca.
- Bahasa ramah, sopan, terstruktur, dan selalu solutif.
"""


# Regex pola kata kunci CS
CS_KEYWORDS_PATTERN = re.compile(
    r"\b(cs|customer\s*service|admin|kontak|hubungi|whatsapp|wa|telepon|no\s*hp|bantuan\s*manusia|agent|call\s*center|sales|paket|bicarakan\s*dengan\s*orang)\b",
    re.IGNORECASE
)

def check_is_cs_requested(text: str) -> bool:
    """Mengecek apakah pertanyaan pengguna mengandung indikasi ingin menghubungi Customer Service."""
    if not text:
        return False
    return bool(CS_KEYWORDS_PATTERN.search(text))

async def query_gemini(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    temperature: float = 0.7
) -> str:
    """
    Mengirimkan prompt ke Google Gemini API menggunakan httpx asynchronous client.
    Mendukung fallback model otomatis jika model utama mengalami kendala.
    """
    contents = []
    
    # Masukkan konteks sistem dan persona sebagai pesan awal
    contents.append({
        "role": "user",
        "parts": [{"text": f"Instruksi Sistem & Basis Pengetahuan:\n{SYSTEM_KNOWLEDGE}\n\nMohon patuhi instruksi di atas dalam setiap jawabanmu."}]
    })
    contents.append({
        "role": "model",
        "parts": [{"text": "Dimengerti! Saya ReconBot, Asisten AI resmi ReconAuto.ID. Saya siap membantu menjawab pertanyaan seputar platform, rekonsiliasi, akuntansi, pertanyaan umum, dan mengarahkan ke Customer Service jika dibutuhkan."}]
    })
    
    # Masukkan riwayat percakapan sebelumnya (jika ada, maksimal 8 riwayat terakhir)
    if history:
        for turn in history[-8:]:
            role = turn.get("role", "user")
            # Map role ke Gemini standard ('user' atau 'model')
            api_role = "model" if role in ["assistant", "model", "bot"] else "user"
            text_val = turn.get("text") or turn.get("content", "")
            if text_val:
                contents.append({
                    "role": api_role,
                    "parts": [{"text": text_val}]
                })
                
    # Tambahkan pesan pengguna saat ini
    contents.append({
        "role": "user",
        "parts": [{"text": prompt}]
    })
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 1024,
            "topP": 0.95
        }
    }
    
    def _call_gemini_sync() -> str:
        import urllib.request
        import ssl
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        models_to_try = [PRIMARY_MODEL] + FALLBACK_MODELS
        last_error = None
        
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=28, context=ctx) as resp:
                    if resp.status == 200:
                        res_json = json.loads(resp.read().decode("utf-8"))
                        candidates = res_json.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
            except urllib.error.HTTPError as e:
                logger.warning(f"Gemini model {model} returned HTTPError {e.code}. Trying next model...")
                last_error = f"HTTP {e.code}"
                continue
            except Exception as e:
                logger.warning(f"Error calling Gemini model {model}: {e}. Trying fallback...")
                last_error = str(e)
                continue
                
        logger.error(f"Semua panggilan Gemini gagal. Error terakhir: {last_error}")
        return fallback_local_reply(prompt)

    return await asyncio.to_thread(_call_gemini_sync)


def fallback_local_reply(prompt: str) -> str:
    """Respons aturan cerdas offline jika koneksi eksternal Google sementara tidak tersedia."""
    lower = prompt.lower()
    if check_is_cs_requested(prompt):
        return (
            "Tentu! Anda dapat langsung terhubung dengan tim **Customer Service ReconAuto.ID**.\n\n"
            f"**WhatsApp CS**: [{CS_INFO['whatsapp_display']}]({CS_INFO['whatsapp_url']})\n"
            f"✉️ **Email**: {CS_INFO['email']}\n"
            f"⏰ **Jam Operasional**: {CS_INFO['hours']}\n\n"
            "Silakan klik tombol WhatsApp yang tersedia untuk memulai percakapan langsung dengan tim kami!"
        )
    if "proof of cash" in lower or "keseimbangan" in lower or "selisih" in lower:
        return (
            "**Proof of Cash (Pembuktian Kas)** adalah formula audit matematis yang memvalidasi bahwa seluruh aliran kas di rekening koran bank terhitung 100% tanpa ada dana gelap tak bertuan (**Formula Kas Tied Rp 0.00**).\n\n"
            "**Mengapa di hasil demo tetap ada selisih operasional?**\n"
            "Status *'Tied Rp 0.00'* menandakan formula pembukuan tertutup sempurna. Di saat bersamaan, sistem secara presisi mengisolasi seluruh selisih riil operasional (seperti *Missing Payout* Rp 7.277.900, *Kasir Shortage* Rp 200.000, dan *Unidentified Deposit* Rp 500.000) agar dapat segera Anda klaim dan tindak lanjuti melalui tabel temuan & generator surat sengketa resmi."
        )
    if "cod" in lower or "kurir" in lower or "jne" in lower or "sicepat" in lower:
        return (
            "**Rekonsiliasi 3-Arah COD** mencocokkan data antara **Order Penjualan**, **Manifest Resi Kurir (AWB)**, "
            "dan **Mutasi Kredit Bank**.\n\n"
            "Sistem otomatis mendeteksi kebocoran kas:\n"
            "- **COD_UNREMITTED**: Paket terkirim tapi dana belum disetor kurir ke rekening bank.\n"
            "- **COD_SHORTAGE**: Setoran kurir lebih kecil daripada nilai tagihan COD (kurang setor)."
        )
    if "demo" in lower:
        return (
            "Anda dapat langsung mencoba fitur rekonsiliasi tanpa perlu menyiapkan data sendiri! "
            "Klik tombol **'Demo 1-Klik Multi-Sumber'** di bagian atas navbar untuk memuat otomatis 8 berkas contoh."
        )
    return (
        "Halo! Saya **ReconBot**, asisten AI ReconAuto.ID. Saya siap membantu Anda mengenai fitur rekonsiliasi multi-bank, "
        "marketplace, payment gateway, audit COD 3-arah, maupun pertanyaan lainnya. "
        "Jika butuh bantuan langsung dari staf kami, Anda juga dapat meminta untuk diarahkan ke **Customer Service** kapan saja."
    )

def clean_chatbot_reply(text: str) -> str:
    """
    Membersihkan kode-kode teknis mentah seperti ###, $$, \\text{}, 
    atau format LaTeX agar teks chat tampil bersih, rapi, dan mudah dibaca.
    """
    if not text:
        return ""
        
    cleaned = text
    
    # 1. Bersihkan LaTeX format $$...$$ atau \\[...\\]
    def _clean_math(match):
        math_content = match.group(1)
        # Hapus \\text{...} -> ...
        math_content = re.sub(r"\\text\{([^}]+)\}", r"\1", math_content)
        # Hapus perintah backslash LaTeX lainnya
        math_content = re.sub(r"\\[a-zA-Z]+", " ", math_content)
        math_content = " ".join(math_content.split())
        return f"\n{math_content}\n"

    cleaned = re.sub(r"\$\$(.*?)\$\$", _clean_math, cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\\\[(.*?)\\\]", _clean_math, cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\\\((.*?)\\\)", _clean_math, cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\$([^$]+)\$", r"\1", cleaned)
    
    # Bersihkan sisa \\text{...} jika ada
    cleaned = re.sub(r"\\text\{([^}]+)\}", r"\1", cleaned)
    
    # 2. Bersihkan header markdown seperti '### 📊', '### 🚀', '### 📐', '### ', '## ', '# '
    cleaned = re.sub(r"^#{1,6}\s*(.*)$", r"**\1**", cleaned, flags=re.MULTILINE)
    
    # 3. Bersihkan garis horizontal berlebih (---)
    cleaned = re.sub(r"^\s*[-*_]{3,}\s*$", "", cleaned, flags=re.MULTILINE)
    
    # 4. Rapikan baris kosong beruntun
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    
    return cleaned.strip()

async def generate_chat_response(
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    active_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Fungsi utama pemroses pesan chat.
    Menerima pesan, memproses dengan Gemini AI, mendeteksi kebutuhan CS, dan menyusun quick actions.
    """
    cleaned_msg = message.strip()
    if not cleaned_msg:
        return {
            "status": "error",
            "reply": "Pesan tidak boleh kosong.",
            "suggest_cs": False,
            "cs_info": CS_INFO,
            "quick_actions": ["Apa itu Proof of Cash?", "Bagaimana cara kerja rekonsiliasi COD?", "Hubungi CS WhatsApp"]
        }
        
    is_cs = check_is_cs_requested(cleaned_msg)
    
    # Dapatkan jawaban dari Gemini & bersihkan format kodenya
    raw_reply = await query_gemini(cleaned_msg, history=history)
    reply_text = clean_chatbot_reply(raw_reply)
    
    # Tentukan rekomendasi aksi cepat berikutnya
    quick_actions = []
    if is_cs:
        quick_actions = ["Buka WhatsApp CS", "Apa saja fitur ReconAuto.ID?", "Coba Demo 1-Klik"]
    else:
        quick_actions = ["Apa itu Proof of Cash?", "Bagaimana audit COD 3-arah?", "Hubungi CS WhatsApp", "Coba Demo 1-Klik"]
        
    return {
        "status": "success",
        "reply": reply_text,
        "suggest_cs": is_cs,
        "cs_info": CS_INFO,
        "quick_actions": quick_actions
    }

