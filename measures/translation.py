from modeltranslation.translator import TranslationOptions, register

from .models import Measure, Picture, Tag


@register(Measure)
class MeasureTranslationOptions(TranslationOptions):
    fields = ("title", "summary", "description")


@register(Tag)
class TagTranslationOptions(TranslationOptions):
    # Only the display name is translated; the slug stays language-neutral
    # because it is used as the filter key in the map/table JavaScript.
    fields = ("name",)


@register(Picture)
class PictureTranslationOptions(TranslationOptions):
    fields = ("caption",)
