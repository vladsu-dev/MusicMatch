from django.core.management.base import BaseCommand
from django.utils import timezone

from music.models import LoginSession, RateBucket


class Command(BaseCommand):
    help = "Delete expired login sessions and rate-limit buckets."

    def handle(self, *args, **options):
        sessions, _ = LoginSession.objects.filter(expires_at__lt=timezone.now()).delete()
        buckets, _ = RateBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted sessions={sessions}, rate_buckets={buckets}"))
