from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Runs tasks.no_purchase_notice"

    def handle(self, *args, **options):
        raise NotImplementedError("This task has been disabled.")
        # from tasks.no_purchase_notice import run_no_purchase_notice
        # run_no_purchase_notice()
