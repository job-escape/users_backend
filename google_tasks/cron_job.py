from rest_framework.decorators import api_view
from rest_framework.response import Response
from tasks.charge_users import run_charge_users
import logging

@api_view(['POST'])
def charge_users_scheduler_view(request):
    """
    Trigger `run_charge_users` via Google Cloud Scheduler.
    """
    if request.method != 'POST':
        return Response({'error': 'Only POST requests are allowed.'}, status=405)

    try:
        run_charge_users()
        logging.debug("Google Cloud Scheduler triggered `run_charge_users` successfully.")
        return Response(status=200)
    except Exception as e:
        logging.error(f"Error running `run_charge_users`: {str(e)}")
        return Response(status=500)