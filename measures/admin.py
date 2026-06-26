from django.contrib import admin
from django.utils.html import format_html

from .models import Measure, Picture, Tag


class PictureInline(admin.TabularInline):
    model = Picture
    extra = 1
    fields = ("image", "thumbnail", "caption", "is_preview", "order")
    readonly_fields = ("thumbnail",)

    @admin.display(description="Preview")
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height:80px;" />', obj.image.url)
        return ""


@admin.register(Measure)
class MeasureAdmin(admin.ModelAdmin):
    list_display = ("title", "lat", "lng", "tag_list")
    list_filter = ("tags",)
    search_fields = ("title", "summary", "description")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    inlines = [PictureInline]

    @admin.display(description="Tags")
    def tag_list(self, obj):
        return ", ".join(t.name for t in obj.tags.all())


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "color", "measure_count")
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)

    @admin.display(description="Measures")
    def measure_count(self, obj):
        return obj.measures.count()
