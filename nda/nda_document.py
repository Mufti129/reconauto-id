"""
Teks lengkap Perjanjian Kerahasiaan (NDA) Digital untuk ReconAuto.ID.

Dokumen ini ditampilkan kepada pengguna sebelum mereka mengunggah data
keuangan ke sistem rekonsiliasi. Persetujuan dicatat secara digital
(timestamp, IP, tanda tangan) sebagai bukti hukum elektronik yang sah
berdasarkan UU ITE No. 11/2008 jo. No. 19/2016 dan PP No. 71/2019.

Hash SHA-256 dari teks NDA digunakan untuk memastikan versi dokumen
yang disetujui pengguna dapat diverifikasi kapan saja (audit trail).
"""

import hashlib

NDA_DOCUMENT_VERSION = "1.0.0"

NDA_DOCUMENT_TEXT = """
PERJANJIAN KERAHASIAAN DATA (NON-DISCLOSURE AGREEMENT)
LAYANAN REKONSILIASI KAS DIGITAL — RECONAUTO.ID

Nomor Perjanjian : NDA/RA/{consent_id}
Tanggal Berlaku  : {tanggal_persetujuan}

═══════════════════════════════════════════════════════════════════════

PARA PIHAK YANG MENGIKATKAN DIRI:

PIHAK PERTAMA (Penyedia Layanan):
Nama        : ReconAuto.ID
Alamat      : [Alamat Terdaftar Penyedia Layanan]
Diwakili oleh: Mukhammad Rekza Mufti (Penanggung Jawab Teknis)
Selanjutnya disebut sebagai "PIHAK PERTAMA" atau "Penyedia Layanan"

PIHAK KEDUA (Pengguna Layanan):
Nama Lengkap   : {nama_lengkap}
Email          : {email}
Perusahaan/Badan: {nama_perusahaan}
Jabatan        : {jabatan}
Selanjutnya disebut sebagai "PIHAK KEDUA" atau "Pengguna"

Secara bersama-sama disebut "Para Pihak" dan masing-masing disebut
"Pihak".

═══════════════════════════════════════════════════════════════════════

MENGINGAT BAHWA:

a. PIHAK PERTAMA adalah penyedia layanan platform rekonsiliasi kas
   dua arah multi-kanal berbasis web yang dikenal sebagai
   "ReconAuto.ID";

b. PIHAK KEDUA bermaksud menggunakan layanan ReconAuto.ID untuk
   memproses data keuangan yang bersifat rahasia dan sensitif,
   termasuk namun tidak terbatas pada: mutasi rekening bank, laporan
   settlement marketplace, laporan payment gateway, data transaksi
   POS, dan dokumen keuangan terkait lainnya;

c. Para Pihak memahami pentingnya menjaga kerahasiaan data keuangan
   dan sepakat untuk mengikatkan diri dalam perjanjian kerahasiaan
   ini demi melindungi kepentingan bersama;

MAKA PARA PIHAK SEPAKAT UNTUK MENGIKATKAN DIRI DALAM PERJANJIAN
KERAHASIAAN BERIKUT:

═══════════════════════════════════════════════════════════════════════

PASAL 1 — DEFINISI

1.1 "Data Rahasia" adalah seluruh informasi keuangan, data transaksi,
    mutasi perbankan, laporan settlement, data rekonsiliasi, serta
    setiap informasi lain yang diunggah, diinput, diproses, atau
    dihasilkan oleh PIHAK KEDUA melalui platform ReconAuto.ID,
    termasuk namun tidak terbatas pada:
    a. Data mutasi rekening bank (CSV, XLSX, PDF);
    b. Laporan settlement marketplace (Shopee, Tokopedia, TikTok
       Shop, Lazada, Blibli, Bukalapak, dan lainnya);
    c. Laporan settlement payment gateway (Midtrans, Xendit, DOKU,
       dan lainnya);
    d. Data transaksi e-wallet dan QRIS;
    e. Data settlement COD logistik;
    f. Data transaksi POS/kasir;
    g. Laporan Proof of Cash dan temuan anomali yang dihasilkan
       sistem;
    h. Setiap dokumen klaim dispute yang di-generate oleh sistem;
    i. Metadata terkait seluruh data di atas (nama file, ukuran,
       timestamp unggah, parameter rekonsiliasi).

1.2 "Platform" adalah sistem perangkat lunak berbasis web
    ReconAuto.ID yang menyediakan layanan rekonsiliasi kas otomatis.

1.3 "Pemrosesan" adalah setiap tindakan terhadap Data Rahasia
    termasuk penyimpanan sementara, analisis, pencocokan,
    normalisasi, dan penghapusan.

1.4 "Data Pribadi" merujuk pada definisi sebagaimana dimaksud dalam
    Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data
    Pribadi (UU PDP).

═══════════════════════════════════════════════════════════════════════

PASAL 2 — RUANG LINGKUP KERAHASIAAN

2.1 Perjanjian ini mencakup seluruh Data Rahasia yang diunggah,
    diinput, atau dihasilkan oleh PIHAK KEDUA selama menggunakan
    Platform, baik dalam format digital maupun turunannya.

2.2 Kewajiban kerahasiaan berlaku sejak tanggal persetujuan
    perjanjian ini dan berlanjut selama PIHAK KEDUA menggunakan
    Platform, serta tetap berlaku selama 2 (dua) tahun setelah
    PIHAK KEDUA berhenti menggunakan Platform atau setelah seluruh
    Data Rahasia dihapus dari sistem, mana yang lebih lama.

2.3 Perjanjian ini berlaku untuk seluruh sesi rekonsiliasi yang
    dilakukan oleh PIHAK KEDUA, baik menggunakan data sampel (demo)
    maupun data riil perusahaan.

═══════════════════════════════════════════════════════════════════════

PASAL 3 — KEWAJIBAN PIHAK PERTAMA (PENYEDIA LAYANAN)

PIHAK PERTAMA berkomitmen dan menjamin bahwa:

3.1 KERAHASIAAN DATA
    a. Tidak akan mengungkapkan, menyebarluaskan, menjual,
       menyewakan, atau memindahtangankan Data Rahasia milik
       PIHAK KEDUA kepada pihak ketiga mana pun tanpa persetujuan
       tertulis dari PIHAK KEDUA;
    b. Tidak akan menggunakan Data Rahasia untuk tujuan apa pun
       selain pelaksanaan layanan rekonsiliasi yang diminta oleh
       PIHAK KEDUA;
    c. Tidak akan melakukan agregasi, analisis statistik, atau
       pembuatan profil dari Data Rahasia untuk kepentingan
       komersial PIHAK PERTAMA.

3.2 KEAMANAN TEKNIS
    a. Seluruh pemrosesan Data Rahasia dilakukan di sisi server
       (backend) dan tidak pernah dikirimkan ke layanan pihak
       ketiga kecuali yang secara eksplisit diperlukan untuk
       fungsionalitas yang diminta pengguna (misal: API chatbot
       untuk pertanyaan umum, yang TIDAK menerima Data Rahasia);
    b. Data Rahasia disimpan dalam basis data terenkripsi di server
       yang dikelola dengan standar keamanan industri;
    c. Akses ke Data Rahasia dibatasi hanya kepada personel teknis
       PIHAK PERTAMA yang terikat kewajiban kerahasiaan internal
       dan hanya untuk keperluan pemeliharaan sistem;
    d. Transmisi data antara perangkat PIHAK KEDUA dan server
       Platform menggunakan protokol enkripsi TLS/SSL.

3.3 NOTIFIKASI INSIDEN
    a. Dalam hal terjadi pelanggaran keamanan (data breach) yang
       berpotensi mengungkapkan Data Rahasia, PIHAK PERTAMA wajib
       memberitahukan PIHAK KEDUA dalam waktu paling lambat
       3 x 24 jam sejak insiden terdeteksi;
    b. Notifikasi meliputi: deskripsi insiden, jenis data yang
       terdampak, langkah mitigasi yang telah dan akan diambil,
       serta kontak penanggung jawab insiden.

═══════════════════════════════════════════════════════════════════════

PASAL 4 — KEWAJIBAN PIHAK KEDUA (PENGGUNA)

PIHAK KEDUA menyatakan dan menjamin bahwa:

4.1 Data yang diunggah ke Platform adalah data yang sah dan PIHAK
    KEDUA memiliki wewenang yang cukup untuk memproses data
    tersebut melalui Platform;

4.2 PIHAK KEDUA bertanggung jawab atas keamanan kredensial akses
    (username, password, token) ke Platform dan tidak akan
    membagikannya kepada pihak yang tidak berwenang;

4.3 PIHAK KEDUA memahami bahwa penggunaan fitur "Demo 1-Klik"
    menggunakan data sampel yang disediakan sistem dan bukan data
    riil perusahaan;

4.4 PIHAK KEDUA tidak akan melakukan reverse engineering, dekompilasi,
    atau upaya lain untuk mengakses kode sumber Platform di luar
    yang disediakan secara resmi.

═══════════════════════════════════════════════════════════════════════

PASAL 5 — PENGECUALIAN KERAHASIAAN

Kewajiban kerahasiaan sebagaimana dimaksud dalam Pasal 2 dan 3
TIDAK berlaku terhadap informasi yang:

5.1 Telah menjadi informasi publik bukan karena pelanggaran
    perjanjian ini oleh salah satu Pihak;

5.2 Telah dimiliki secara sah oleh Pihak penerima sebelum
    pengungkapan berdasarkan perjanjian ini, dibuktikan dengan
    catatan tertulis;

5.3 Diperoleh secara sah dari pihak ketiga yang tidak terikat
    kewajiban kerahasiaan terhadap informasi tersebut;

5.4 Wajib diungkapkan berdasarkan perintah pengadilan, lembaga
    pemerintah yang berwenang, atau ketentuan peraturan
    perundang-undangan yang berlaku, dengan ketentuan bahwa Pihak
    yang diwajibkan mengungkapkan akan memberitahukan Pihak lainnya
    secepat mungkin sebelum pengungkapan dilakukan;

5.5 Dikembangkan secara independen oleh Pihak penerima tanpa
    menggunakan atau merujuk Data Rahasia Pihak pengungkap.

═══════════════════════════════════════════════════════════════════════

PASAL 6 — JANGKA WAKTU, PENGHAPUSAN DATA & RETENSI

6.1 PENYIMPANAN DATA
    a. Data Rahasia yang diunggah PIHAK KEDUA disimpan di server
       Platform selama PIHAK KEDUA aktif menggunakan layanan;
    b. Riwayat sesi rekonsiliasi (session history) disimpan dalam
       basis data SQLite Platform dan dapat diakses kembali oleh
       PIHAK KEDUA kapan saja selama akun aktif.

6.2 PENGHAPUSAN DATA
    a. PIHAK KEDUA berhak meminta penghapusan seluruh Data Rahasia
       miliknya dari server Platform kapan saja dengan mengirimkan
       permintaan tertulis ke alamat email yang tercantum;
    b. PIHAK PERTAMA akan melaksanakan penghapusan dalam waktu
       paling lambat 14 (empat belas) hari kerja sejak permintaan
       diterima;
    c. Setelah penghapusan, PIHAK PERTAMA akan memberikan
       konfirmasi tertulis bahwa seluruh Data Rahasia telah
       dihapus secara permanen dari seluruh sistem, termasuk
       backup.

6.3 RETENSI OTOMATIS
    a. Apabila PIHAK KEDUA tidak melakukan aktivitas apa pun pada
       Platform selama 90 (sembilan puluh) hari kalender
       berturut-turut, PIHAK PERTAMA berhak menghapus Data
       Rahasia secara otomatis setelah memberikan pemberitahuan
       melalui email 14 hari sebelumnya;
    b. File yang diunggah untuk pemrosesan rekonsiliasi (CSV, XLSX,
       PDF) akan dihapus secara otomatis dari server dalam waktu
       24 jam setelah pemrosesan selesai; hanya hasil rekonsiliasi
       (metadata dan ringkasan) yang dipertahankan di basis data.

═══════════════════════════════════════════════════════════════════════

PASAL 7 — GANTI RUGI & TANGGUNG JAWAB

7.1 Dalam hal PIHAK PERTAMA terbukti melanggar kewajiban kerahasiaan
    sebagaimana diatur dalam Perjanjian ini, PIHAK PERTAMA
    bertanggung jawab atas kerugian langsung yang diderita PIHAK
    KEDUA yang dapat dibuktikan secara wajar sebagai akibat langsung
    dari pelanggaran tersebut.

7.2 Tanggung jawab PIHAK PERTAMA tidak mencakup:
    a. Kerugian tidak langsung, insidental, atau konsekuensial;
    b. Kehilangan keuntungan yang diharapkan (lost profit);
    c. Kerugian yang timbul akibat kelalaian PIHAK KEDUA sendiri
       dalam menjaga keamanan kredensial akses;
    d. Kerugian akibat force majeure (bencana alam, perang,
       gangguan infrastruktur telekomunikasi nasional, kebijakan
       pemerintah yang tidak dapat dihindari).

7.3 PIHAK PERTAMA TIDAK menjamin keakuratan hasil rekonsiliasi yang
    dihasilkan Platform. Hasil rekonsiliasi bersifat bantu analisis
    dan PIHAK KEDUA tetap bertanggung jawab untuk memverifikasi
    hasil sebelum mengambil keputusan bisnis atau hukum berdasarkan
    hasil tersebut.

═══════════════════════════════════════════════════════════════════════

PASAL 8 — HUKUM YANG BERLAKU & PENYELESAIAN SENGKETA

8.1 Perjanjian ini tunduk pada dan ditafsirkan berdasarkan hukum
    Negara Republik Indonesia.

8.2 Perjanjian ini disusun dengan memperhatikan ketentuan:
    a. Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan
       Data Pribadi (UU PDP);
    b. Undang-Undang Nomor 11 Tahun 2008 tentang Informasi dan
       Transaksi Elektronik sebagaimana diubah dengan
       Undang-Undang Nomor 19 Tahun 2016 (UU ITE);
    c. Peraturan Pemerintah Nomor 71 Tahun 2019 tentang
       Penyelenggaraan Sistem dan Transaksi Elektronik;
    d. Kitab Undang-Undang Hukum Perdata (KUHPerdata) Buku III
       tentang Perikatan.

8.3 Setiap perselisihan yang timbul dari atau sehubungan dengan
    Perjanjian ini akan diselesaikan terlebih dahulu secara
    musyawarah untuk mufakat dalam waktu 30 (tiga puluh) hari
    kalender. Apabila musyawarah tidak mencapai kesepakatan, Para
    Pihak sepakat untuk menyelesaikan perselisihan melalui
    Badan Arbitrase Nasional Indonesia (BANI) yang putusannya
    bersifat final dan mengikat.

═══════════════════════════════════════════════════════════════════════

PASAL 9 — PERSETUJUAN ELEKTRONIK

9.1 PIHAK KEDUA menyatakan bahwa persetujuan yang diberikan secara
    elektronik melalui Platform (berupa centang kotak persetujuan
    dan/atau tanda tangan digital pada layar) memiliki kekuatan
    hukum yang sama dengan tanda tangan basah sebagaimana diatur
    dalam UU ITE dan PP 71/2019.

9.2 Sebagai bukti persetujuan, sistem mencatat:
    a. Identitas PIHAK KEDUA (nama, email, perusahaan, jabatan);
    b. Waktu persetujuan (timestamp UTC dan WIB);
    c. Alamat IP perangkat yang digunakan;
    d. User-Agent browser;
    e. Hash SHA-256 dari teks perjanjian yang disetujui (untuk
       memastikan versi dokumen dapat diverifikasi);
    f. Data tanda tangan digital (jika disediakan).

9.3 Record persetujuan disimpan oleh PIHAK PERTAMA sebagai bagian
    dari audit trail dan dapat diakses oleh PIHAK KEDUA melalui
    endpoint verifikasi yang disediakan Platform.

═══════════════════════════════════════════════════════════════════════

DENGAN MENCENTANG KOTAK PERSETUJUAN DAN/ATAU MEMBUBUHKAN TANDA
TANGAN DIGITAL DI BAWAH INI, PIHAK KEDUA MENYATAKAN TELAH MEMBACA,
MEMAHAMI, DAN MENYETUJUI SELURUH KETENTUAN DALAM PERJANJIAN
KERAHASIAAN INI.

Persetujuan ini berlaku efektif sejak tanggal dan waktu yang tercatat
oleh sistem pada saat PIHAK KEDUA menyelesaikan proses persetujuan
elektronik.

═══════════════════════════════════════════════════════════════════════
Versi Dokumen   : {versi_dokumen}
Hash Dokumen    : {hash_dokumen}
═══════════════════════════════════════════════════════════════════════
""".strip()


def _compute_template_hash() -> str:
    """Hitung SHA-256 dari template NDA (sebelum placeholder diisi).
    Hash ini menjadi identitas versi dokumen untuk audit trail."""
    return hashlib.sha256(NDA_DOCUMENT_TEXT.encode("utf-8")).hexdigest()


NDA_DOCUMENT_HASH = _compute_template_hash()


def render_nda(
    consent_id: str = "—",
    tanggal_persetujuan: str = "—",
    nama_lengkap: str = "—",
    email: str = "—",
    nama_perusahaan: str = "—",
    jabatan: str = "—",
) -> str:
    """Render teks NDA dengan data pengguna yang sudah terisi."""
    return NDA_DOCUMENT_TEXT.format(
        consent_id=consent_id,
        tanggal_persetujuan=tanggal_persetujuan,
        nama_lengkap=nama_lengkap,
        email=email,
        nama_perusahaan=nama_perusahaan or "—",
        jabatan=jabatan or "—",
        versi_dokumen=NDA_DOCUMENT_VERSION,
        hash_dokumen=NDA_DOCUMENT_HASH,
    )
