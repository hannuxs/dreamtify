"""
Data awal (idempoten — aman dijalankan berulang):
SiteSetting, rekening, grup Owner/Admin + permission, FAQ, template pesan.
"""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import BankAccount, FaqItem, SiteSetting
from apps.notifications.defaults import DEFAULT_TEMPLATES
from apps.notifications.models import MessageTemplate

# docs/referensi/form-jaswar-jastip.md
BANK_ACCOUNTS = [("BCA", "7805519240", "Norma Anissa Yuliana")]

REFUND_SUMMARY = (
    "Fee jasa dibayar penuh di awal. Batal = fee hangus. Tiket tidak didapat = uang kembali 100% "
    "dikurangi booking slot per tiket. Gagal karena VA tidak dibayar tepat waktu = fee tidak kembali."
)

# docs/04 §7
FAQ = [
    ("Apa beda JASWAR dan JASTIP?",
     "JASWAR (jasa war saja): tim kami ikut war memakai data kamu, lalu gelang/tiket fisik kamu tukar sendiri.\n"
     "JASTIP (terima beres): tim kami war memakai data tim Dreamtify, menukarkan tiket sampai dapat gelang, "
     "lalu menyerahkannya ke kamu."),
    ("Kapan saya tahu tiket dapat atau tidak?",
     "Hasil per tiket langsung tampil di halaman lacak pesanan begitu tim mengisinya saat war. "
     "Kami juga mengabari lewat WhatsApp setelah war."),
    ("Bagaimana kalau tidak dapat tiket?",
     "Uang kamu dikembalikan 100% dikurangi biaya booking slot per tiket (umumnya Rp50.000). "
     "Isi rekening refund di halaman lacak, lalu kami transfer."),
    ("Kenapa harus pilih kategori cadangan?",
     "Saat war, kategori bisa habis dalam hitungan detik. Dengan cadangan, tim langsung pindah ke pilihan "
     "berikutnya tanpa menunggu konfirmasi, jadi peluang dapat tiket lebih besar. Bila semua pilihan habis, "
     "tim boleh mengamankan kategori lain yang tersedia."),
    ("Apa itu titip bayar & kenapa nominalnya kategori termahal?",
     "Titip bayar artinya kamu menitipkan uang harga tiket ke kami, jadi kamu tidak perlu standby saat war. "
     "Kami pakai harga kategori termahal di antara pilihanmu agar uangnya pasti cukup. "
     "Selisihnya kami kembalikan setelah war."),
    ("Bisa pesan untuk teman / beberapa kategori?",
     "Bisa. Di form pesanan, tekan \"Tambah tiket\" untuk menambah kategori atau pemegang tiket lain. "
     "Semua masuk dalam satu pesanan dan satu kali bayar."),
    ("Bagaimana kalau saya batal?",
     "Kamu bisa membatalkan sendiri dari halaman lacak sebelum war dimulai. Fee jasa yang sudah dibayar hangus, "
     "sedangkan uang harga tiket (titip bayar) dikembalikan. Sejak war dimulai, pesanan tidak bisa dibatalkan."),
    ("Apakah data KTP saya aman?",
     "Data KTP dienkripsi di sistem kami, hanya dipakai untuk pembelian tiket, dan dihapus otomatis "
     "setelah event selesai."),
    ("Berapa lama refund diproses?",
     "Refund diproses setelah war selesai dan rekening refund kamu terisi. Bukti transfer refund bisa dilihat "
     "di halaman lacak pesanan."),
]

# Aplikasi yang permission-nya dikelola grup
APP_LABELS = ("core", "events", "orders", "notifications", "testimonials")

# Admin = operasional (docs/03 "Pengguna & peran")
ADMIN_PERMS = {
    "events": ("add", "change", "view"),
    "orders": ("add", "change", "view"),
    "notifications": ("change", "view"),
    "testimonials": ("add", "change", "delete", "view"),
}
ADMIN_CORE_VIEW = ("view_bankaccount", "view_faqitem", "view_sitesetting")
# Hanya Owner (docs/09 §2)
OWNER_ONLY_PERMS = {"view_full_nik"}


class Command(BaseCommand):
    help = "Isi data awal (idempoten): pengaturan, rekening, grup & izin, FAQ, template pesan."

    @transaction.atomic
    def handle(self, *args, **options):
        setting = SiteSetting.load()
        if not setting.refund_policy_summary:
            setting.refund_policy_summary = REFUND_SUMMARY
            setting.save(update_fields=["refund_policy_summary", "updated_at"])
        self.stdout.write("[OK] Pengaturan situs")

        for i, (bank, number, holder) in enumerate(BANK_ACCOUNTS):
            BankAccount.objects.get_or_create(bank_name=bank, account_number=number,
                                              defaults={"account_holder": holder, "sort_order": i})
        self.stdout.write("[OK] Rekening")

        if not FaqItem.objects.exists():
            FaqItem.objects.bulk_create(
                [FaqItem(question=q, answer=a, sort_order=i) for i, (q, a) in enumerate(FAQ)])
            self.stdout.write("[OK] FAQ awal")
        else:
            self.stdout.write("[LEWATI] FAQ sudah ada")

        created = updated = 0
        for key, (title, body, send_email) in DEFAULT_TEMPLATES.items():
            tpl, was_created = MessageTemplate.objects.get_or_create(
                key=key, defaults={"title": title, "body": body, "send_email": send_email})
            if was_created:
                created += 1
            elif not tpl.is_customized and (tpl.body, tpl.title) != (body, title):
                tpl.title, tpl.body = title, body
                tpl.save(update_fields=["title", "body", "updated_at"])
                updated += 1
        self.stdout.write(f"[OK] Template pesan ({created} baru, {updated} diperbarui)")

        self._groups()
        self.stdout.write("[OK] Grup Owner & Admin")

    def _groups(self):
        owner, _ = Group.objects.get_or_create(name="Owner")
        admin, _ = Group.objects.get_or_create(name="Admin")

        owner_perms = Permission.objects.filter(content_type__app_label__in=APP_LABELS) | \
            Permission.objects.filter(content_type__app_label="auth", content_type__model="user")
        owner.permissions.set(owner_perms)

        admin_perms = []
        for app, actions in ADMIN_PERMS.items():
            for perm in Permission.objects.filter(content_type__app_label=app):
                if perm.codename in OWNER_ONLY_PERMS:
                    continue
                if perm.codename.split("_", 1)[0] in actions:
                    admin_perms.append(perm)
        admin_perms += list(Permission.objects.filter(content_type__app_label="core",
                                                      codename__in=ADMIN_CORE_VIEW))
        admin.permissions.set(admin_perms)
