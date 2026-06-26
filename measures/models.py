from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Tag(models.Model):
    class Category(models.TextChoices):
        KIND = "kind", _("Type")        # N/T/D/S — drives marker colour
        GOAL = "goal", _("Goal")        # thematic goals, filtered separately
        SOURCE = "source", _("Source")  # manual / survey
        OTHER = "other", _("Other")

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    # Optional hex colour (e.g. "#2c7fb8") for chips / markers.
    color = models.CharField(max_length=7, blank=True, default="")
    category = models.CharField(
        max_length=10, choices=Category.choices, default=Category.OTHER,
        help_text="Groups the tag into a filter section; 'Type' tags colour the map markers.",
    )

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Measure(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(help_text="Full text shown on the detail page.")
    summary = models.CharField(
        "goal", max_length=300, blank=True,
        help_text="The measure's goal — used as the map hover/preview text and detail-page lead.",
    )
    lat = models.FloatField("latitude")
    lng = models.FloatField("longitude")
    tags = models.ManyToManyField(Tag, related_name="measures", blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "measure"
            slug = base
            n = 2
            while Measure.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("measures:detail", args=[self.slug])

    def preview_picture(self):
        """The picture used for the map/preview thumbnail."""
        return self.pictures.filter(is_preview=True).first() or self.pictures.first()


class Picture(models.Model):
    measure = models.ForeignKey(Measure, related_name="pictures", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="measures/%Y/%m/")
    caption = models.CharField(max_length=200, blank=True)
    is_preview = models.BooleanField(
        default=False, help_text="Use this picture as the map/preview thumbnail."
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.caption or f"Picture #{self.pk}"
