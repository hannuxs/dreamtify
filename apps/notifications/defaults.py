"""
Template pesan default (docs/08 §3). Dipakai `seed_initial` dan sebagai
cadangan bila template di DB belum ada. Semua menyertakan {kode} & {link_lacak}.
"""

# key: (judul, isi, kirim_email)
DEFAULT_TEMPLATES = {
    "PESANAN_DIBUAT": (
        "Pesanan dibuat",
        "Halo kak {nama} ☁️\n"
        "Pesanan *{kode}* ({event} – {tahap}) sudah kami catat.\n\n"
        "Tagihan sekarang: *{nominal}*\n"
        "Bayar sebelum: *{batas_waktu}*\n\n"
        "Rekening tujuan:\n{rekening}\n\n"
        "Upload bukti transfer & pantau pesanan di:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "WAITING_LIST_MASUK": (
        "Masuk waiting list",
        "Halo kak {nama} ☁️\n"
        "Kuota {event} – {tahap} sedang penuh, jadi pesanan *{kode}* masuk *waiting list* dulu ya.\n"
        "Kakak belum perlu bayar apa pun. Kami kabari begitu ada slot.\n\n"
        "Pantau di: {link_lacak}\n\n— {brand}",
        True,
    ),
    "WAITING_LIST_NAIK": (
        "Naik dari waiting list",
        "Kabar baik kak {nama}! 🎉\n"
        "Pesanan *{kode}* ({event} – {tahap}) dapat slot dari waiting list.\n\n"
        "Tagihan fee: *{nominal}*\n"
        "Bayar sebelum: *{batas_waktu}* (lewat dari itu slot dilepas)\n\n"
        "Rekening tujuan:\n{rekening}\n\n"
        "Upload bukti di: {link_lacak}\n\n— {brand}",
        True,
    ),
    "PENGINGAT_FEE": (
        "Pengingat bayar fee",
        "Halo kak {nama}, pengingat ya ⏰\n"
        "Fee pesanan *{kode}* ({event}) sebesar *{nominal}* belum kami terima.\n"
        "Batas bayar: *{batas_waktu}*. Lewat batas, pesanan otomatis dibatalkan.\n\n"
        "Upload bukti di: {link_lacak}\n\n— {brand}",
        True,
    ),
    "FEE_DITERIMA": (
        "Fee diterima",
        "Halo kak {nama} ☁️\n"
        "Pembayaran fee untuk pesanan *{kode}* ({event} – {tahap}) sudah kami terima. Slot kakak aman!\n\n"
        "Langkah berikutnya bisa dicek di sini:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "BUKTI_DITOLAK": (
        "Bukti ditolak",
        "Halo kak {nama}, bukti transfer untuk *{kode}* belum bisa kami terima: {alasan}.\n"
        "Mohon upload ulang di {link_lacak} ya kak 🙏\n\n— {brand}",
        True,
    ),
    "TAGIHAN_PELUNASAN": (
        "Tagihan pelunasan",
        "Halo kak {nama} ☁️\n"
        "Untuk pesanan *{kode}* ({event} – {tahap}), pelunasan harga tiket (titip bayar) sebesar *{nominal}*.\n"
        "Bayar sebelum: *{batas_waktu}*.\n\n"
        "Nominal ini dari kategori termahal pilihan kakak; selisihnya kami kembalikan setelah war.\n\n"
        "Rekening tujuan:\n{rekening}\n\n"
        "Upload bukti di: {link_lacak}\n\n— {brand}",
        True,
    ),
    "PENGINGAT_PELUNASAN": (
        "Pengingat pelunasan",
        "Halo kak {nama}, pengingat pelunasan ⏰\n"
        "Pesanan *{kode}* ({event}) masih kurang *{nominal}*.\n"
        "Batas pelunasan: *{batas_waktu}*. Lewat batas, slot dioper ke waiting list.\n\n"
        "Upload bukti di: {link_lacak}\n\n— {brand}",
        True,
    ),
    "SIAP_WAR": (
        "Siap war",
        "Yeay kak {nama}, pesanan *{kode}* sudah *siap war* 🎫\n"
        "{event} – {tahap}, war: *{batas_waktu}*.\n\n"
        "Tiket kakak:\n{ringkasan_tiket}\n\n"
        "Kalau pakai VA, mohon standby saat war ya. Pantau di:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "VA_DIKIRIM": (
        "VA dikirim",
        "Kak {nama}, VA untuk pesanan *{kode}* sudah keluar! ⏰\n"
        "Bank: {va_bank}\n"
        "No. VA: *{va_nomor}*\n"
        "Nominal: *{nominal}*\n"
        "Bayar sebelum: *{va_batas}*\n\n"
        "Setelah bayar, tekan \"Sudah saya bayar\" di:\n{link_lacak}\n"
        "Telat bayar = tiket hangus & fee tidak kembali ya kak 🙏",
        False,
    ),
    "HASIL_SECURED": (
        "Hasil war: dapat",
        "Selamat kak {nama}! 🎉 Hasil war {event} untuk pesanan *{kode}*:\n{ringkasan_hasil}\n\n"
        "Detail & langkah berikutnya:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "HASIL_SEBAGIAN": (
        "Hasil war: sebagian",
        "Halo kak {nama}, hasil war {event} untuk pesanan *{kode}*:\n{ringkasan_hasil}\n\n"
        "Kelebihan bayar akan kami refund. Mohon isi rekening refund di:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "HASIL_GAGAL": (
        "Hasil war: belum dapat",
        "Halo kak {nama}, mohon maaf 🙏 hasil war {event} untuk pesanan *{kode}*:\n{ringkasan_hasil}\n\n"
        "Uang kakak kami kembalikan sesuai ketentuan (dipotong booking slot). "
        "Mohon isi rekening refund di:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "REFUND_ISI_REKENING": (
        "Isi rekening refund",
        "Halo kak {nama}, ada refund *{nominal}* untuk pesanan *{kode}*.\n"
        "Mohon isi rekening tujuan refund di:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "REFUND_SELESAI": (
        "Refund ditransfer",
        "Halo kak {nama}, refund *{nominal}* untuk pesanan *{kode}* sudah kami transfer ✅\n"
        "Bukti transfer bisa dilihat di:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "KEKURANGAN_BAYAR": (
        "Kekurangan bayar",
        "Halo kak {nama}, untuk pesanan *{kode}* ({event}) masih ada kekurangan *{nominal}* "
        "karena kategori yang didapat lebih mahal dari pilihan.\n\n"
        "Rekening tujuan:\n{rekening}\n\n"
        "Upload bukti di: {link_lacak}\n\n— {brand}",
        True,
    ),
    "GELANG_SIAP": (
        "Gelang siap diserahkan",
        "Halo kak {nama} ☁️ Gelang untuk pesanan *{kode}* ({event}) siap diserahkan!\n"
        "{detail_penyerahan}\n\n"
        "Detail: {link_lacak}\n\n— {brand}",
        True,
    ),
    "ETIKET_INFO": (
        "Info penukaran tiket",
        "Halo kak {nama} ☁️ Info tiket untuk pesanan *{kode}* ({event}) sudah tersedia.\n"
        "{detail_penyerahan}\n\n"
        "Unduh e-tiket / baca cara penukaran gelang di:\n{link_lacak}\n\n— {brand}",
        True,
    ),
    "DIBATALKAN": (
        "Pesanan dibatalkan",
        "Halo kak {nama}, pesanan *{kode}* ({event} – {tahap}) dibatalkan: {alasan}.\n"
        "Bila ada dana yang kembali, kami proses sesuai ketentuan.\n\n"
        "Detail: {link_lacak}\n\n— {brand}",
        True,
    ),
    "SELESAI_MINTA_TESTIMONI": (
        "Selesai & minta testimoni",
        "Terima kasih kak {nama}! ✨ Pesanan *{kode}* ({event}) sudah selesai.\n"
        "Kalau berkenan, ceritakan pengalaman kakak bersama {brand} lewat halaman lacak:\n{link_lacak}\n\n"
        "Sampai jumpa di war berikutnya ☁️",
        True,
    ),
}

# Hanya email (customer sudah melihat halaman sukses) — docs/08 §3
EMAIL_ONLY_KEYS = {"PESANAN_DIBUAT", "WAITING_LIST_MASUK"}
# Mendesak → hanya WA
WA_ONLY_KEYS = {"VA_DIKIRIM"}
RESULT_KEYS = {"HASIL_SECURED", "HASIL_SEBAGIAN", "HASIL_GAGAL"}
