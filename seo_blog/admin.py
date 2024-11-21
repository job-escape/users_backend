from django.contrib import admin
import nested_admin
from .models import (ImageComponent, TextComponent, 
                     VideoComponent, ButtonComponent, 
                     Blog, BlogCategory, BlogComponent)
# Register your models here.


admin.site.register(BlogCategory)

class BlogComponentInline(nested_admin.NestedStackedPolymorphicInline):
    class ImageComponentInline(nested_admin.NestedStackedPolymorphicInline.Child):
        model = ImageComponent

    class VideoComponentInline(nested_admin.NestedStackedPolymorphicInline.Child):
        model = VideoComponent

    class TextComponentInline(nested_admin.NestedStackedPolymorphicInline.Child):
        model = TextComponent
    
    class ButtonComponentInline(nested_admin.NestedStackedPolymorphicInline.Child):
        model = ButtonComponent

    model = BlogComponent
    child_inlines = (
        ImageComponentInline,
        VideoComponentInline,
        TextComponentInline,
        ButtonComponentInline
    )
    classes = ['collapse']


@admin.register(Blog)
class BlogAdmin(nested_admin.NestedPolymorphicModelAdmin):
    inlines = (BlogComponentInline,)