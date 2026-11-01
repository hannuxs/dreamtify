"""
Data demo untuk mencoba web (`dev.bat seed`). HANYA untuk DJANGO_ENV=dev.
2 event, ±25 pesanan di semua status, hasil war, refund, penyerahan, testimoni.
Semua perubahan lewat services agar datanya sama seperti pemakaian sungguhan.
"""
import io
from datetime import date, timedelta
from itertools import count

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.core.actors import Actor
from apps.core.enums import (
    CancelReason,
    EventStatus,
    FeeTier,
    FulfillmentStatus,
    HandoverMethod,
    PhaseStatus,
    ServiceType,
    SlotResult,
    TicketPaymentMethod,
)
from apps.events.models import Event, FeeRule, SalePhase, TicketCategory
from apps.orders.models import Order, TicketSlot
from apps.orders.services import transitions, updates
from apps.orders.services import va as va_service
from apps.orders.services.links import tracking_url
from apps.orders.services.validation import BuyerData, HolderData, LineData
from apps.testimonials import services as testimonials
from apps.testimonials.models import Testimonial

SLUG_A, SLUG_B = "demo-dreamy-fanmeet", "demo-sky-concert"
DEMO_PASSWORD = "demo-dreamtify-123"
JASWAR, JASTIP = ServiceType.JASWAR, ServiceType.JASTIP
TITIP, VA_BCA, VA_MANDIRI = TicketPaymentMethod.TITIP_BAYAR, TicketPaymentMethod.VA_BCA, TicketPaymentMethod.VA_MANDIRI
CUSTOMER = Actor(label="customer demo", kind="customer")

NAMES = ["Rina Putri", "Budi Santoso", "Sari Dewi", "Dimas Pratama", "Nadia Kusuma", "Fajar Nugroho", "Ayu Lestari",
         "Reza Maulana", "Citra Anggraini", "Bagas Wicaksono", "Maya Safitri", "Yoga Permana", "Tari Wulandari",
         "Ilham Ramadhan", "Dinda Puspita", "Galih Saputra", "Laras Pertiwi", "Arif Hidayat", "Vina Oktavia",
         "Kevin Halim", "Mega Rahayu", "Andre Wijaya", "Putri Amalia", "Rizky Firmansyah", "Salsa Nabila", "Hana Pertiwi"]


def picture(text: str, size=(800, 600), top=(136, 181, 214), bottom=(253, 228, 231)) -> bytes:
    """Gambar contoh sederhana (gradasi + tulisan) tanpa aset tambahan."""
    w, h = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(h):
        mix = y / h
        draw.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * mix) for a, b in zip(top, bottom)))
    draw.text((w // 12, h // 2), text, fill=(5, 42, 69), font_size=max(20, w // 16))
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=82)
    return buf.getvalue()


class Demo:
    def __init__(self, actor):
        self.actor = actor
        self.seq = count(1)

    def event(self, slug, name, cats, *, artist, venue, city, dates):
        event = Event.objects.create(
            name=name, slug=slug, artist=artist, venue=venue, city=city, event_dates=dates,
            first_show_date=timezone.localdate() + timedelta(days=45), status=EventStatus.TAMPIL,
            ticketing_platform="Tiket resmi promotor", promotor_name="Promotor Contoh", promotor_link_enabled=True,
            description="Event contoh untuk mencoba web ini. Data ini bukan event sungguhan.",
            redemption_info="Tukar gelang di booth penukaran H-1 sampai hari acara, bawa KTP asli.")
        event.poster.save(f"{slug}.jpg", ContentFile(picture(name, (800, 1000))), save=True)
        categories = {}
        for i, (cat_name, tier, price) in enumerate(cats):
            categories[cat_name] = TicketCategory.objects.create(event=event, name=cat_name, fee_tier=tier, price=price,
                                                                 sort_order=i)
        return event, categories

    def phase(self, event, name, status, *, war_in, order=0, quota=None):
        now = timezone.now()
        phase = SalePhase.objects.create(
            event=event, name=name, status=status, sort_order=order, slot_quota=quota,
            order_open_at=now - timedelta(days=3), order_close_at=now + war_in - timedelta(hours=3),
            war_at=now + war_in, pelunasan_deadline=now + war_in - timedelta(days=1))
        for service, tier, fee in ((JASWAR, FeeTier.VIP, 250_000), (JASWAR, FeeTier.REGULER, 200_000),
                                   (JASTIP, FeeTier.VIP, 300_000), (JASTIP, FeeTier.REGULER, 250_000)):
            FeeRule.objects.create(phase=phase, service_type=service, fee_tier=tier, fee_per_ticket=fee)
        return phase

    def order(self, phase, cats, spec, *, method=TITIP, hours_ago=48):
        """spec: [(layanan, jumlah, [kategori])]. Nama & NIK contoh diambil berurutan."""
        n = next(self.seq)
        name = NAMES[(n - 1) % len(NAMES)]
        first = name.split()[0].lower()
        buyer = BuyerData(name=name, whatsapp=f"08123{n:07d}", email=f"{first}{n}@contoh.test", instagram=f"{first}_{n}",
                          referral="@teman_dreamtify" if n % 5 == 0 else "")
        lines = []
        for index, (service, qty, names) in enumerate(spec):
            ids = [cats[c].pk for c in names]
            holder_name = name if index == 0 else NAMES[(n + 10 + index) % len(NAMES)]
            holder_wa = f"08123{n:07d}"
            if service == JASWAR:
                holder = HolderData(name=holder_name, whatsapp=holder_wa, email=buyer.email,
                                    nik=f"3171{n:06d}{index:02d}0001"[:16], gender="P" if n % 2 else "L",
                                    birth_date=date(1998 + n % 6, 1 + n % 12, 1 + n % 27), instagram=buyer.instagram)
            else:
                holder = HolderData(name=holder_name, whatsapp=holder_wa)
            lines.append(LineData(service_type=service, quantity=qty, primary=ids[0], backup1=ids[1], backup2=ids[2],
                                  holder=holder))
        order = transitions.create_order(phase=phase, buyer=buyer, lines=lines, payment_method=method, actor=CUSTOMER,
                                         enforce_schedule=False)
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(hours=hours_ago + n))
        order.refresh_from_db()
        return order

    def send(self, order, amount):
        proof = ContentFile(picture("BUKTI TRANSFER (CONTOH)"), name="bukti.jpg")
        return transitions.submit_payment(order, amount=amount, actor=CUSTOMER, sender_name=order.buyer_name,
                                          sender_bank="BCA", transfer_date=timezone.localdate(), proof=proof)

    def pay(self, order, amount):
        transitions.verify_payment(self.send(order, amount), actor=self.actor)
        order.refresh_from_db()
        return order

    def slots(self, order):
        return list(TicketSlot.objects.filter(line__order=order).select_related("line__order")
                    .order_by("line__sort_order", "index"))

    def result(self, order, cats, *results):
        """results per tiket: nama kategori (secured), "GAGAL", "VA" (gagal customer)."""
        for slot, value in zip(self.slots(order), results):
            if value == "GAGAL":
                transitions.set_slot_result(slot, SlotResult.GAGAL, actor=self.actor)
            elif value == "VA":
                transitions.set_slot_result(slot, SlotResult.GAGAL_CUSTOMER, actor=self.actor)
            else:
                transitions.set_slot_result(slot, SlotResult.SECURED, actor=self.actor, category=cats[value],
                                            ticket_reference=f"TKT-{slot.pk:05d}")
        order.refresh_from_db()

    def account(self, order):
        updates.set_refund_account(order, bank="BCA", number=f"12{order.pk:08d}", holder=order.buyer_name, actor=CUSTOMER)

    def jastip_done(self, order):
        for slot in self.slots(order):
            if slot.result != SlotResult.SECURED:
                continue
            transitions.set_fulfillment(slot, FulfillmentStatus.DITUKAR, actor=self.actor)
            transitions.set_fulfillment(slot, FulfillmentStatus.SIAP_DISERAHKAN, actor=self.actor,
                                        method=HandoverMethod.TITIK_TEMU, detail="Lobby venue, H-1 pukul 15.00")
            transitions.set_fulfillment(slot, FulfillmentStatus.DISERAHKAN, actor=self.actor, receiver_name=order.buyer_name)
        order.refresh_from_db()

    def jaswar_done(self, order):
        for slot in self.slots(order):
            if slot.result == SlotResult.SECURED:
                transitions.set_fulfillment(slot, FulfillmentStatus.INFO_DIKIRIM, actor=self.actor,
                                            note="Tukar gelang di booth A, bawa KTP asli.")
        order.refresh_from_db()


def remove_demo(stdout):
    events = Event.objects.filter(slug__in=(SLUG_A, SLUG_B))
    orders = Order.objects.filter(event__in=events)
    for t in Testimonial.objects.filter(event__in=events):
        testimonials.delete(t, actor=Actor.system())
    for order in orders.prefetch_related("payments", "va_notices"):
        for payment in order.payments.all():
            if payment.proof:
                payment.proof.delete(save=False)
    orders.delete()
    for event in events:
        if event.poster:
            event.poster.delete(save=False)
        event.delete()
    stdout.write("[OK] Data demo lama dihapus")


class Command(BaseCommand):
    help = "Isi data demo (hanya DJANGO_ENV=dev). --reset menghapus data demo lama dulu."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Hapus data demo lama lalu buat ulang")

    def handle(self, *args, **options):
        if settings.DJANGO_ENV != "dev":
            raise CommandError("seed_demo hanya boleh dijalankan saat DJANGO_ENV=dev.")
        call_command("seed_initial", verbosity=0, stdout=io.StringIO())
        if Event.objects.filter(slug__in=(SLUG_A, SLUG_B)).exists():
            if not options["reset"]:
                self.stdout.write("[LEWATI] Data demo sudah ada. Pakai --reset untuk membuat ulang.")
                return
            remove_demo(self.stdout)
        with transaction.atomic():
            owner = self._user("demo-owner", "Owner")
            self._user("demo-admin", "Admin")
            result = self._build(Actor.staff(owner, ip="127.0.0.1"))
        self.stdout.write(self.style.SUCCESS(f"[OK] Data demo dibuat: {Order.objects.filter(event__slug__in=(SLUG_A, SLUG_B)).count()} pesanan"))
        self.stdout.write(f"     Login /kelola/: demo-owner atau demo-admin, sandi {DEMO_PASSWORD}")
        self.stdout.write(f"     Pesanan SELESAI siap diberi testimoni: {tracking_url(result)}")

    def _user(self, username, role):
        user, _ = get_user_model().objects.get_or_create(username=username, defaults={"is_staff": True})
        user.set_password(DEMO_PASSWORD)
        user.save()
        user.groups.add(Group.objects.get(name=role))
        return user

    def _build(self, actor):
        demo = Demo(actor)
        pending_testimonial = self._event_a(demo)
        self._event_b(demo)
        self._manual_testimonials(actor)
        return pending_testimonial

    def _event_a(self, demo):
        """Contoh docs/02 §4.5: Presale sudah selesai, Gensale sedang war."""
        d = demo
        event, cats = d.event(SLUG_A, "Dreamy Fanmeet (Demo)", [
            ("Duality Package", FeeTier.VIP, 3_500_000), ("CAT 1", FeeTier.REGULER, 2_500_000),
            ("CAT 2", FeeTier.REGULER, 2_000_000), ("CAT 3", FeeTier.REGULER, 1_500_000),
        ], artist="Dreamy", venue="Istora Senayan", city="Jakarta", dates="20 Des 2026")
        presale = d.phase(event, "Presale", PhaseStatus.BUKA, war_in=timedelta(days=3), order=0)
        top = ["Duality Package", "CAT 1", "CAT 2"]
        low = ["CAT 3", "CAT 2", "CAT 1"]

        secured_top = d.pay(d.order(presale, cats, [(JASWAR, 2, top)]), 7_500_000)  # contoh 1: dapat Duality + CAT 1
        all_failed = d.pay(d.order(presale, cats, [(JASWAR, 2, top)]), 7_500_000)  # contoh 2: refund 7,4 jt
        failed_paid = d.pay(d.order(presale, cats, [(JASWAR, 1, low)], method=VA_BCA), 200_000)
        short = d.pay(d.order(presale, cats, [(JASWAR, 1, low)]), 2_700_000)  # contoh 3: kekurangan 1,05 jt
        customer_fail = d.pay(d.order(presale, cats, [(JASWAR, 1, top)], method=VA_MANDIRI), 250_000)
        jastip_ready = d.pay(d.order(presale, cats, [(JASTIP, 2, low)]), 5_500_000)
        jastip_done = d.pay(d.order(presale, cats, [(JASTIP, 1, low)]), 2_750_000)
        jaswar_done = d.pay(d.order(presale, cats, [(JASWAR, 1, low)], method=VA_BCA), 200_000)
        jaswar_done2 = d.pay(d.order(presale, cats, [(JASWAR, 2, low)], method=VA_MANDIRI), 400_000)
        mixed = d.pay(d.order(presale, cats, [(JASWAR, 1, top), (JASTIP, 1, low)]), 6_550_000)

        transitions.start_war(presale, actor=d.actor)
        d.result(secured_top, cats, "Duality Package", "CAT 1")
        d.result(all_failed, cats, "GAGAL", "GAGAL")
        d.result(failed_paid, cats, "GAGAL")
        d.result(short, cats, "Duality Package")
        d.result(customer_fail, cats, "VA")
        d.result(jastip_ready, cats, "CAT 3", "CAT 3")
        d.result(jastip_done, cats, "CAT 3")
        d.result(jaswar_done, cats, "CAT 3")
        d.result(jaswar_done2, cats, "CAT 2", "CAT 3")
        d.result(mixed, cats, "CAT 1", "GAGAL")
        transitions.finish_war(presale, actor=d.actor)

        d.account(all_failed)
        d.account(failed_paid)
        transitions.record_refund(failed_paid, amount=150_000, actor=d.actor, transfer_date=timezone.localdate(),
                                  proof=ContentFile(picture("BUKTI REFUND (CONTOH)"), name="refund.jpg"))
        d.jastip_done(jastip_done)
        d.account(jastip_done)  # selisih titipan: dapat CAT 3, titip harga CAT 1
        transitions.record_refund(jastip_done, amount=1_000_000, actor=d.actor, transfer_date=timezone.localdate())
        d.jaswar_done(jaswar_done)
        d.jaswar_done(jaswar_done2)
        for slot in d.slots(jastip_ready):
            transitions.set_fulfillment(slot, FulfillmentStatus.DITUKAR, actor=d.actor)

        for order, name, rating, text, photo in (
            (jastip_done, "Kak Reza", 5, "Terima beres beneran. Gelang sampai tangan H-1, tinggal nonton.", True),
            (jaswar_done, "Kak Vina", 5, "Hasil war langsung kelihatan di halaman lacak, jadi tenang.", False),
        ):
            testimonial = testimonials.submit_from_customer(
                order, display_name=name, rating=rating, text=text, actor=CUSTOMER,
                image=ContentFile(picture("Foto gelang (contoh)"), name="foto.jpg") if photo else None)
            testimonials.approve(testimonial, actor=d.actor)
            testimonials.toggle_featured(testimonial, actor=d.actor)

        now = timezone.now()
        SalePhase.objects.filter(pk=presale.pk).update(
            war_at=now - timedelta(days=4), order_close_at=now - timedelta(days=5),
            pelunasan_deadline=now - timedelta(days=5), order_open_at=now - timedelta(days=9),
            war_started_at=now - timedelta(days=4), war_finished_at=now - timedelta(days=4) + timedelta(hours=1))

        gensale = d.phase(event, "Gensale", PhaseStatus.BUKA, war_in=timedelta(days=2), order=1)
        va_order = d.pay(d.order(gensale, cats, [(JASWAR, 2, low)], method=VA_BCA, hours_ago=20), 400_000)
        titip_order = d.pay(d.order(gensale, cats, [(JASTIP, 1, top)], hours_ago=20), 3_800_000)
        third = d.pay(d.order(gensale, cats, [(JASWAR, 1, low)], method=VA_MANDIRI, hours_ago=20), 200_000)
        transitions.start_war(gensale, actor=d.actor)
        d.result(third, cats, "CAT 2")
        va_service.create_va_notice(va_order, bank="BCA", va_number="8808123456789012", amount=3_000_000, actor=d.actor,
                                    expires_at=timezone.now() + timedelta(hours=2),
                                    slot_ids=[s.pk for s in d.slots(va_order)])
        SalePhase.objects.filter(pk=gensale.pk).update(
            war_at=now - timedelta(minutes=30), order_close_at=now - timedelta(hours=3),
            pelunasan_deadline=now - timedelta(days=1), war_started_at=now - timedelta(minutes=30))
        assert titip_order
        return jaswar_done2

    def _event_b(self, demo):
        """Presale masih buka: semua status sebelum war, termasuk waiting list & batal."""
        d = demo
        event, cats = d.event(SLUG_B, "Sky Concert (Demo)", [
            ("VIP", FeeTier.VIP, 4_000_000), ("Festival", FeeTier.REGULER, 2_200_000),
            ("Tribune", FeeTier.REGULER, 1_400_000),
        ], artist="The Sky", venue="Beach City Stadium", city="Jakarta", dates="10–11 Jan 2027")
        presale = d.phase(event, "Presale", PhaseStatus.BUKA, war_in=timedelta(days=5), order=0)
        d.phase(event, "Gensale", PhaseStatus.DRAFT, war_in=timedelta(days=12), order=1)
        vip = ["VIP", "Festival", "Tribune"]
        reg = ["Festival", "Tribune", "VIP"]

        d.order(presale, cats, [(JASWAR, 1, reg)], hours_ago=2)  # MENUNGGU_FEE
        d.order(presale, cats, [(JASTIP, 2, reg)], method=VA_BCA, hours_ago=3)
        d.send(d.order(presale, cats, [(JASWAR, 2, vip)], method=VA_BCA, hours_ago=4), 500_000)  # VERIFIKASI_FEE
        d.pay(d.order(presale, cats, [(JASWAR, 1, vip)], hours_ago=6), 250_000)  # MENUNGGU_PELUNASAN
        d.pay(d.order(presale, cats, [(JASTIP, 1, reg)], hours_ago=7), 300_000)
        checking = d.pay(d.order(presale, cats, [(JASWAR, 1, reg)], hours_ago=8), 250_000)
        d.send(checking, 4_000_000)  # VERIFIKASI_PELUNASAN
        d.pay(d.order(presale, cats, [(JASWAR, 2, reg)], method=VA_MANDIRI, hours_ago=9), 500_000)  # SIAP_WAR
        d.pay(d.order(presale, cats, [(JASTIP, 1, vip)], hours_ago=10), 4_300_000)
        transitions.cancel_by_customer(d.order(presale, cats, [(JASWAR, 1, reg)], hours_ago=11), actor=CUSTOMER)  # DIBATALKAN
        transitions.cancel_by_customer(d.pay(d.order(presale, cats, [(JASWAR, 1, reg)], method=VA_BCA, hours_ago=12), 250_000),
                                       actor=CUSTOMER)  # HANGUS
        transitions.cancel_by_admin(d.pay(d.order(presale, cats, [(JASWAR, 1, reg)], method=VA_BCA, hours_ago=13), 250_000),
                                    actor=d.actor, reason=CancelReason.BATAL_ADMIN)

        used = 11
        presale.slot_quota = used
        presale.save(update_fields=["slot_quota"])
        d.order(presale, cats, [(JASWAR, 2, reg)], hours_ago=1)  # kuota penuh → WAITING_LIST
        presale.slot_quota = used + 8  # ada slot lepas: admin bisa mencoba "Naikkan" dari waiting list
        presale.save(update_fields=["slot_quota"])

    def _manual_testimonials(self, actor):
        event = Event.objects.get(slug=SLUG_A)
        rows = [
            ("Kak Nadia", 5, "Adminnya sabar, dijawab cepat, dan tiketnya dapat kategori utama!", True),
            ("Kak Dimas", 4, "Sempat deg-degan tapi ternyata dapat CAT 2. Refund selisihnya juga cepat.", False),
            ("Kak Ayu", 5, "Baru pertama pakai jastip, prosesnya jelas dari awal sampai gelang di tangan.", True),
            ("Kak Bagas", 5, "Pesan buat bertiga sekali bayar, praktis banget.", False),
            ("Kak Maya", 4, "Tidak dapat tiket tapi refund masuk sesuai yang dijanjikan.", False),
        ]
        for i, (name, rating, text, featured) in enumerate(rows):
            image = ContentFile(picture("Screenshot chat (contoh)", (600, 800)), name="chat.jpg") if i == 2 else None
            testimonial = testimonials.create_manual(display_name=name, rating=rating, text=text, event=event,
                                                     image=image, actor=actor)
            if featured:
                testimonials.toggle_featured(testimonial, actor=actor)
        Testimonial.objects.create(display_name="Kak Laras", event=event, rating=5, consent_publish=True,
                                   text="Menunggu dicek admin, coba setujui dari dashboard ya.")
        hidden = testimonials.create_manual(display_name="Kak Galih", rating=3, text="Contoh testimoni yang disembunyikan.",
                                            event=event, actor=actor)
        testimonials.hide(hidden, actor=actor)
