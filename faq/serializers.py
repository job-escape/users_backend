
from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer

from .models import (ContactForm, ImageComponent, Question, TextComponent,
                     VideoComponent)


class AnswerTextComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextComponent
        fields = ['id', 'order', 'content']


class AnswerVideoComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoComponent
        fields = ['id', 'order', 'video']


class AnswerImageComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageComponent
        fields = ['id', 'order', 'image']


class AnswerComponentSerializer(PolymorphicSerializer):
    resource_type_field_name = 'component_type'
    model_serializer_mapping = {
        ImageComponent: AnswerImageComponentSerializer,
        VideoComponent: AnswerVideoComponentSerializer,
        TextComponent: AnswerTextComponentSerializer,
    }


class QuestionSerializer(serializers.ModelSerializer):
    components = AnswerComponentSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'order', 'question', 'components']


class ContactFormSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactForm
        fields = '__all__'
