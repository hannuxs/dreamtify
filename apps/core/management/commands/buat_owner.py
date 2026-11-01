"""Buat akun Owner pertama (dipanggil install.bat). Lewati bila sudah ada Owner aktif."""
import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Buat akun Owner. Tanpa --username: bertanya di layar. Sandi juga bisa dari env DREAMTIFY_OWNER_PASSWORD."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="")

    def handle(self, *args, **options):
        User = get_user_model()
        group = Group.objects.filter(name="Owner").first()
        if group is None:
            raise CommandError("Grup Owner belum ada. Jalankan siapkan_db dulu.")
        if User.objects.filter(is_active=True, groups=group).exists():
            self.stdout.write("[LEWATI] Akun Owner sudah ada")
            return
        username = options["username"] or input("Username Owner: ").strip()
        if not username:
            raise CommandError("Username wajib diisi.")
        if User.objects.filter(username=username).exists():
            raise CommandError(f"Username '{username}' sudah dipakai.")
        password = os.environ.get("DREAMTIFY_OWNER_PASSWORD") or self._ask_password()
        try:
            validate_password(password, User(username=username))
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        user = User.objects.create_superuser(username=username, password=password, email="")
        user.groups.add(group)
        self.stdout.write(self.style.SUCCESS(f"[OK] Akun Owner '{username}' dibuat"))

    def _ask_password(self) -> str:
        first = getpass.getpass("Sandi Owner (min. 10 karakter): ")
        if first != getpass.getpass("Ulangi sandi: "):
            raise CommandError("Kedua sandi tidak sama.")
        return first
