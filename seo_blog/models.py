# seo_blog/models.py

from django.db import models
from django.utils.timezone import now
from polymorphic.models import PolymorphicModel
from rest_framework.fields import MinValueValidator
from tinymce import models as t_models


class BlogCategory(models.Model):
    name = models.CharField(verbose_name="Category name", max_length=25, null=True, blank=True)

    def __str__(self):
        return str(self.name)


class Blog(models.Model):
    category = models.ManyToManyField(BlogCategory, verbose_name="Categories")
    title = models.CharField(verbose_name="Title", max_length=100, null=True, blank=True)
    link_name = models.CharField(verbose_name="Link Name", max_length=100, null=True, blank=True)
    order = models.PositiveIntegerField(default=1, verbose_name="Order of the blog", validators=[MinValueValidator(1)])
    short_description = t_models.HTMLField(verbose_name="Short description", default="", blank=True)
    long_description = t_models.HTMLField(verbose_name="Long description", default="", blank=True)
    author = models.CharField(verbose_name="Author", max_length=50, null=True, blank=True)
    publish_date = models.DateTimeField(verbose_name="Date and Time of publish", default=now)
    keywords = models.CharField(verbose_name="Keywords", max_length=1000, null=True, blank=True)
    duration = models.IntegerField(default=5, verbose_name="Reading duration")
    image = models.ImageField(verbose_name="Image", upload_to='blog/images/', max_length=100, null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Blog[{self.pk}] {self.title}"


class BlogComponent(PolymorphicModel):
    question = models.ForeignKey(Blog, related_name="components", verbose_name="Blog", on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=1, verbose_name="Order of the Component", validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['order']


class ImageComponent(BlogComponent):
    image = models.ImageField(verbose_name="Image", upload_to='blog/images/', max_length=100, null=True, blank=True)


class VideoComponent(BlogComponent):
    video = models.FileField(verbose_name="Video", upload_to='blog/videos/', max_length=100, null=True, blank=True)


class TextComponent(BlogComponent):
    content = t_models.HTMLField(verbose_name="Text with HTML Tags", default="", blank=True)


class ButtonComponent(BlogComponent):
    text = models.CharField(verbose_name="Button text", max_length=100, null=True, blank=True)
    url = models.CharField(verbose_name="Button URL", max_length=300, null=True, blank=True)
