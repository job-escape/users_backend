from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Runs tasks.payment_notice"

    def handle(self, *args, **options):
        raise NotImplementedError("This task has been disabled.")
        from tasks.payment_notice import run_payment_notice
        run_payment_notice()
