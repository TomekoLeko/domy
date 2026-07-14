"""
Anonimizacja danych osobowych (PII) w lokalnej bazie po zaciagnieciu kopii produkcji.

Uruchamiac WYLACZNIE na lokalnej/dev bazie, np. po `heroku pg:pull`.
Komenda odmawia dzialania, gdy wykryje srodowisko produkcyjne lub host bazy
wskazujacy na produkcje (Heroku Postgres).
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Wspolne, jawnie testowe haslo dla wszystkich kont po anonimizacji.
DEFAULT_PASSWORD = "haslo123"

# Hosty uznawane za produkcyjne (Heroku Postgres dziala na AWS RDS).
PRODUCTION_HOST_SUFFIXES = ("amazonaws.com", "herokuapp.com")


class Command(BaseCommand):
    help = "Anonimizuje dane osobowe w lokalnej bazie (uzytkownicy, profile, wysylki, platnosci)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Pomija pytanie o potwierdzenie (do uzycia w skryptach).",
        )
        parser.add_argument(
            "--keep-superusers",
            action="store_true",
            help="Nie zmienia hasla/danych kont superuser (zostawia dostep administracyjny).",
        )

    def handle(self, *args, **options):
        self._guard_not_production()

        if not options["yes"]:
            confirm = input(
                "Ta operacja NADPISZE dane osobowe w bazie '%s'. Kontynuowac? [t/N]: "
                % settings.DATABASES["default"].get("NAME", "?")
            )
            if confirm.strip().lower() not in {"t", "tak", "y", "yes"}:
                self.stdout.write(self.style.WARNING("Przerwano."))
                return

        with transaction.atomic():
            users_count = self._anonymize_users(options["keep_superusers"])
            profiles_count = self._anonymize_profiles()
            shipments_count = self._anonymize_shipments()
            payments_count = self._anonymize_payments()

        self.stdout.write(
            self.style.SUCCESS(
                "Anonimizacja zakonczona: uzytkownicy=%d, profile=%d, wysylki=%d, platnosci=%d. "
                "Haslo dla wszystkich kont: '%s'."
                % (users_count, profiles_count, shipments_count, payments_count, DEFAULT_PASSWORD)
            )
        )

    def _guard_not_production(self):
        if getattr(settings, "ENVIRONMENT", "development") == "production":
            raise CommandError("Odmowa: ENVIRONMENT == 'production'.")

        host = str(settings.DATABASES.get("default", {}).get("HOST", "") or "").lower()
        if host and any(host.endswith(suffix) for suffix in PRODUCTION_HOST_SUFFIXES):
            raise CommandError(
                "Odmowa: host bazy (%s) wyglada na produkcyjny." % host
            )

    def _anonymize_users(self, keep_superusers):
        count = 0
        users = User.objects.all()
        for user in users.iterator():
            if keep_superusers and user.is_superuser:
                continue
            user.first_name = "Imie%d" % user.pk
            user.last_name = "Nazwisko%d" % user.pk
            user.email = "user%d@example.test" % user.pk
            user.set_password(DEFAULT_PASSWORD)
            user.save(update_fields=["first_name", "last_name", "email", "password"])
            count += 1
        return count

    def _anonymize_profiles(self):
        from users.models import Profile

        count = 0
        for profile in Profile.objects.iterator():
            profile.name = "Profil %d" % profile.pk if profile.name else profile.name
            profile.address = "ul. Testowa %d" % profile.pk if profile.address else profile.address
            profile.city = "Miasto" if profile.city else profile.city
            profile.postal = "00-000" if profile.postal else profile.postal
            profile.parcel_locker_code = ""
            profile.phone = "500000000" if profile.phone else profile.phone
            profile.save(
                update_fields=[
                    "name",
                    "address",
                    "city",
                    "postal",
                    "parcel_locker_code",
                    "phone",
                ]
            )
            count += 1
        return count

    def _anonymize_shipments(self):
        from shipping.models import Shipment

        count = 0
        for shipment in Shipment.objects.iterator():
            shipment.recipient_name = "Odbiorca %d" % shipment.pk
            shipment.recipient_phone = "500000000"
            shipment.recipient_email = (
                "recipient%d@example.test" % shipment.pk if shipment.recipient_email else ""
            )
            shipment.recipient_postal_code = "00-000"
            shipment.recipient_address = "ul. Testowa %d" % shipment.pk
            shipment.recipient_city = "Miasto"
            shipment.parcel_locker_code = ""
            shipment.notes = ""
            shipment.save(
                update_fields=[
                    "recipient_name",
                    "recipient_phone",
                    "recipient_email",
                    "recipient_postal_code",
                    "recipient_address",
                    "recipient_city",
                    "parcel_locker_code",
                    "notes",
                ]
            )
            count += 1
        return count

    def _anonymize_payments(self):
        from finance.models import Payment

        # `sender` (nadawca) moze zawierac dane osobowe darczyncow.
        count = 0
        for payment in Payment.objects.exclude(sender__isnull=True).exclude(sender="").iterator():
            payment.sender = "Nadawca %d" % payment.pk
            payment.save(update_fields=["sender"])
            count += 1
        return count
