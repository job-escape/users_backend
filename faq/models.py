# faq/models.py

from django.db import models
from polymorphic.models import PolymorphicModel
from rest_framework.fields import MinValueValidator
from tinymce import models as t_models


class Question(models.Model):
    question = models.CharField(verbose_name="Question", max_length=100, null=True, blank=True)
    order = models.PositiveIntegerField(default=1, verbose_name="Order of the question", validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Question[{self.pk}] {self.question}"


class AnswerComponent(PolymorphicModel):
    question = models.ForeignKey(Question, related_name="components", verbose_name="Question", on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=1, verbose_name="Order of the Component", validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["order"]


class ImageComponent(AnswerComponent):
    image = models.ImageField(verbose_name="Image", upload_to="faq/images/", max_length=100, null=True, blank=True)


class VideoComponent(AnswerComponent):
    video = models.FileField(verbose_name="Video", upload_to="faq/videos/", max_length=100, null=True, blank=True)


class TextComponent(AnswerComponent):
    content = t_models.HTMLField(verbose_name="Text with HTML Tags", default="", blank=True)


class ContactForm(models.Model):
    name = models.CharField(verbose_name="Name", max_length=100, null=True, blank=True)
    email = models.CharField(verbose_name="Email", max_length=100, null=True, blank=True)
    message = models.TextField(verbose_name="Text", null=True, blank=True)
    date_created = models.DateTimeField(verbose_name="Date Created", auto_now_add=True)
