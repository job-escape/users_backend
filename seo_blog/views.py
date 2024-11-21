from rest_framework import mixins, viewsets

from .models import Blog, BlogCategory
from .serializers import (BlogCategorySerializer, BlogEmptySerializer,
                          BlogListSerializer, BlogSerializer)


class BlogViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """
        The viewset for retrieving information related to Blogs.
    """
    serializer_class = BlogListSerializer
    pagination_class = None
    queryset = Blog.objects.all().prefetch_related('category')
    lookup_field = 'link_name'

    def get_serializer_class(self):
        if self.action == 'list':
            return BlogListSerializer
        elif self.action == 'retrieve':
            return BlogSerializer
        return BlogEmptySerializer


class BlogCategoryViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
        The viewset for retrieving information related to BlogCaterogies.
    """
    serializer_class = BlogCategorySerializer
    pagination_class = None
    queryset = BlogCategory.objects.all()
