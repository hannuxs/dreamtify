# Asumsi & Keputusan

Dokumen ini berisi keputusan yang diambil saat menyusun spesifikasi.
**File ini prioritas tertinggi**: bila bertentangan dengan dokumen lain,
ikuti file ini. Ubah langsung di sini bila tidak sesuai, lalu beri tahu
Claude Code: *"ASUMSI-DAN-KEPUTUSAN.md sudah saya ubah, sesuaikan."*

Tanda ⚠️ = paling perlu dicek pemilik bisnis.

## A. Dari jawaban pemilik (sudah pasti)

| # | Keputusan |
|---|---|
| A1 | Nama brand **Dreamtify**, tagline "Your Dream is Our Priority", logo di `assets/` |
| A2 | Setiap tiket punya data pemegangnya sendiri (bisa beda dari pemesan) |
| A3 | Customer **tanpa login**. Lacak pesanan dengan **kode pesanan + nomor WA** |
| A4 | Python, web di port **8383**, MariaDB di port **3309**, server **Windows** |
| A5 | 1 perintah instalasi produksi (`install.bat`), 2 perintah jalan (`dev.bat`, `prod.bat`) |
| A6 | JASTIP = tim menukar sampai dapat **gelang** lalu diserahkan. JASWAR = hanya war; customer menukar gelang sendiri |
| A7 | Promotor meminta data dengan **format kolom Google Form jaswar/jastip lama** (lihat `docs/07`) |
| A8 | Wajib ada halaman testimoni |

## B. Diambil dari aturan di Google Form lama

| # | Aturan |
|---|---|
| B1 | Fee jasa per tiket, beda per **tahap** (Presale/Gensale) × **layanan** (Jaswar/Jastip) × **tier** (VIP/Reguler) |
| B2 | Fee jasa dibayar **penuh di awal** |
| B3 | Customer membatalkan = fee **hangus** |
| B4 | Tiket tidak didapat = refund 100% dikurangi **booking slot Rp50.000 per tiket** |
| B5 | Gagal karena kelalaian customer (tidak bayar VA tepat waktu) = **tidak ada refund** fee |
| B6 | Wajib pilih kategori utama + cadangan 1 + cadangan 2 (berbeda). Tim otomatis pindah ke cadangan tanpa konfirmasi; bila semua habis, tim boleh mengamankan kategori apa pun yang tersedia |
| B7 | Metode bayar harga tiket: **VA BCA**, **VA Mandiri** (dibayar customer sendiri saat war, wajib standby), atau **Titip Bayar Admin** (paling lambat H-1 war) |
| B8 | Pelunasan titip bayar = harga **kategori termahal** di antara pilihan × jumlah tiket, dikurangi early booking bila ada |
| B9 | Lewat batas pelunasan → slot dilepas ke waiting list |
| B10 | Customer yang war sendiri dan lebih dulu secured boleh mengirim VA-nya agar dibayarkan tim |
| B11 | Data pemesan/pemegang: nama, WA, email, No. KTP, jenis kelamin, tanggal lahir, username IG, no. membership (opsional), perekomendasi |

## C. Keputusan improvisasi (boleh diubah)

| # | Keputusan | Alasan |
|---|---|---|
| C1 ⚠️ | **Satu pesanan = beberapa "baris tiket"**. Satu baris setara satu isian Google Form lama: 1 pemegang tiket, 1 layanan, jumlah 1–4, kategori utama + 2 cadangan. Contoh: pesan 2 VIP untuk diri sendiri + 1 CAT 3 untuk teman = 2 baris dalam 1 pesanan, 1 kali bayar | Menyelesaikan masalah "beli beberapa kategori / beliin orang lain" dan tetap cocok dengan format promotor |
| C2 ⚠️ | Data pemegang per baris: **JASWAR** wajib lengkap (nama, KTP, JK, tgl lahir, email, WA, IG, membership bila event mewajibkan). **JASTIP** cukup nama + WA penerima gelang (tiket memakai data tim) | Sesuai A6; mengurangi data sensitif yang disimpan |
| C3 ⚠️ | Fee di awal dihitung dari **tier tertinggi** di antara pilihan kategori baris itu. Setelah hasil war, fee disesuaikan dengan kategori yang benar-benar didapat; selisihnya ikut direfund | Konsisten dengan aturan B8 (pakai yang termahal dulu) |
| C4 ⚠️ | Booking slot Rp50.000 dihitung **per tiket** dan bisa diubah per event | Form lama tidak menyebut per tiket/per pesanan |
| C5 ⚠️ | Bila customer membatalkan setelah melunasi titip bayar: **fee hangus, uang harga tiket dikembalikan** | Menahan uang harga tiket terasa tidak adil dan berisiko komplain |
| C6 ⚠️ | Lewat batas pelunasan: admin menekan "Lepas slot". Fee **hangus** (default, bisa diubah per event ke "refund dikurangi booking slot") | Form lama hanya menyebut slot dioper |
| C7 | Bila kuota penuh, pesanan baru masuk **waiting list tanpa membayar dulu**. Saat dinaikkan, customer diberi batas waktu bayar fee (default 24 jam) | Tidak menahan uang orang yang belum pasti dapat slot |
| C8 | Pesanan boleh dibuat tanpa bukti transfer; bukti diupload belakangan di halaman lacak. Batas bayar fee default **24 jam**, lewat itu pesanan otomatis **Dibatalkan** (tidak ada uang yang ditahan) | Customer sering transfer belakangan |
| C9 | Kabar ke customer lewat **tombol WhatsApp click-to-chat** (gratis) dari "Kotak Kabar" admin + email otomatis (opsional, bila SMTP diisi). Disiapkan "pintu" untuk WA gateway berbayar (Fonnte/Wablas) tanpa mengaktifkannya | Tanpa biaya bulanan; halaman lacak sudah mengurangi pertanyaan |
| C10 | Pembayaran tetap **transfer manual + upload bukti**, diverifikasi admin. Opsi "kode unik" nominal (default mati) | Belum ada keputusan payment gateway |
| C11 | Promotor mendapat **link rahasia per event** untuk mengunduh Excel sendiri kapan saja (bisa dinonaktifkan/diganti). Kolom No. KTP hanya disertakan bila Owner mengaktifkannya | Mengurangi promotor menagih rekap |
| C12 | Data NIK & tanggal lahir **dihapus otomatis 30 hari** setelah event selesai (bisa diubah) | UU PDP (UU 27/2022): simpan seperlunya |
| C13 | Peran admin: **Owner** (semua akses, lihat NIK, pengaturan, user) dan **Admin** (operasional: verifikasi, war, hasil, penyerahan, kabar) | Sederhana |
| C14 | Zona waktu tampilan **WIB (Asia/Jakarta)** karena jadwal war umumnya WIB. Bisa diganti di `.env` | Jadwal di form lama memakai WIB |
| C15 | Customer bisa mengirim testimoni dari halaman lacak setelah pesanan selesai; tampil setelah disetujui admin. Admin juga bisa upload testimoni (mis. screenshot chat) | Testimoni jadi mudah terkumpul |
| C16 | Rekening tujuan transfer diatur di Pengaturan (bisa lebih dari satu). Seed awal memakai rekening di form lama (lihat `docs/referensi/`) | |
| C17 | Database dev dan produksi terpisah: `dreamtify_dev` dan `dreamtify` | Aman saat uji coba |
| C18 | HTTPS di luar cakupan aplikasi; dokumen deploy memberi opsi (Cloudflare Tunnel / reverse proxy IIS) | Port 8383 polos HTTP |
