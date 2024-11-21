
from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer

from .models import (Blog, BlogCategory, ButtonComponent, ImageComponent,
                     TextComponent, VideoComponent)


class BlogTextComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextComponent
        fields = ['id', 'order', 'content']


class BlogVideoComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoComponent
        fields = ['id', 'order', 'video']


class BlogImageComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageComponent
        fields = ['id', 'order', 'image']


class BlogButtonComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ButtonComponent
        fields = ['id', 'order', 'text', 'url']


class BlogComponentSerializer(PolymorphicSerializer):
    resource_type_field_name = 'component_type'
    model_serializer_mapping = {
        ImageComponent: BlogImageComponentSerializer,
        VideoComponent: BlogVideoComponentSerializer,
        TextComponent: BlogTextComponentSerializer,
        ButtonComponent: BlogButtonComponentSerializer,
    }


class BlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = '__all__'


class BlogSerializer(serializers.ModelSerializer):
    category = BlogCategorySerializer(many=True, read_only=True)
    components = BlogComponentSerializer(many=True, read_only=True)

    class Meta:
        model = Blog
        fields = '__all__'


class BlogListSerializer(serializers.ModelSerializer):
    category = BlogCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Blog
        fields = ['id', 'order', 'title', 'link_name', 'short_description', 'author', 'publish_date', 'duration', 'category', 'image',]


class BlogEmptySerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = []
