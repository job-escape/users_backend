import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs tasks.payment_notice"

    def handle(self, *args, **options):
        from tasks.charge_users import run_charge_users
        try:
            run_charge_users()
        except Exception as e:
            logger.exception("Checkout: Recurring: Exception!")
            raise e
