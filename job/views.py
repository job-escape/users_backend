from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from custom.custom_permissions import HasUnexpiredSubscription
from job.models import Job, JobUser
from job.serializers import (JobExpiredSerializer, JobListSerializer,
                             JobSerializer, JobUserCreateSerializer,
                             JobUserListSerializer)


class JobViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """The viewset for retrieveing Jobs information."""
    queryset = Job.objects.all()
    permission_classes = [HasUnexpiredSubscription]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            return qs.prefetch_related('company')
        if self.action == 'retrieve':
            return qs.prefetch_related('company', 'similar_jobs__company')
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return JobListSerializer
        if self.action == 'retrieve':
            return JobSerializer
        return JobExpiredSerializer


class JobUserViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """The viewset for interacting with JobUsers."""
    permission_classes = [HasUnexpiredSubscription]

    def get_queryset(self):
        return JobUser.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return JobUserListSerializer
        if self.action == 'create':
            return JobUserCreateSerializer

    def create(self, request, *args, **kwargs):
        """Create or retrieve if already exists."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_ = status.HTTP_201_CREATED
        if JobUser.objects.filter(user=request.user, **serializer.validated_data).exists():
            serializer.instance = JobUser.objects.get(user=request.user, **serializer.validated_data)
            status_ = status.HTTP_200_OK
        serializer.save(user=request.user)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status_, headers=headers)
