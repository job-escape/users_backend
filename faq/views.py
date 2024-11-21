from rest_framework import mixins, viewsets

from .models import Question
from .serializers import ContactFormSerializer, QuestionSerializer
from .utils import createTicket


class FaqViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """The viewset for displaying FAQ info through Questions."""
    serializer_class = QuestionSerializer
    pagination_class = None

    def get_queryset(self):
        return Question.objects.prefetch_related('components').all()


class ContactFormViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    """The viewset for posting a ContactForm and sending a FreshDesk ticket."""
    serializer_class = ContactFormSerializer

    def perform_create(self, serializer):
        serializer.save()
        createTicket(serializer.data)
