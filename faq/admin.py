from django.contrib import admin
from nested_admin import polymorphic

from .models import (AnswerComponent, ContactForm, ImageComponent, Question,
                     TextComponent, VideoComponent)

# Register your models here.


class AnswerComponentInline(polymorphic.NestedStackedPolymorphicInline):
    class ImageComponentInline(polymorphic.NestedStackedPolymorphicInline.Child):
        model = ImageComponent

    class VideoComponentInline(polymorphic.NestedStackedPolymorphicInline.Child):
        model = VideoComponent

    class TextComponentInline(polymorphic.NestedStackedPolymorphicInline.Child):
        model = TextComponent

    model = AnswerComponent
    child_inlines = (
        ImageComponentInline,
        VideoComponentInline,
        TextComponentInline
    )
    classes = ['collapse']


@admin.register(Question)
class UnitAdmin(polymorphic.NestedPolymorphicModelAdmin):
    inlines = (AnswerComponentInline,)


class ContactFormAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'message', 'date_created')
    search_fields = ['name', 'email',]


admin.site.register(ContactForm, ContactFormAdmin)
