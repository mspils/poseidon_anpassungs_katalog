"""Bulk-import measures from a CSV file (multilingual).

Usage:
    python manage.py import_measures path/to/file.csv [--delimiter ';']

Columns (header row required):
    lat, lng                              -- required, numeric
    title, summary, description           -- default-language (Danish) text
    title_da/de/en, summary_da/de/en,
    description_da/de/en                  -- per-language text (override the
                                             plain column for that language)
    tags                                  -- ";"-separated ENGLISH tag names
    slug                                  -- optional explicit measure slug
    image_paths                           -- ";"-separated local file paths

Language handling:
  * A plain column (e.g. "title") fills the default language (da). A suffixed
    column (e.g. "title_de") fills that specific language and wins over the
    plain one. Missing languages fall back to Danish on the site.
  * Tags are given once in English. The slug is derived from the English name
    (language-neutral), and the English text seeds both the English and the
    default-language name so nothing renders blank before it is translated in
    the admin.

Idempotency:
  Measures are matched on slug (explicit "slug" column, else derived from the
  English title, else the default-language title), so re-running updates rather
  than duplicates. Only the fields present in the CSV are touched on an update.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from measures.models import Measure, Picture, Tag

TRANSLATED_FIELDS = ("title", "summary", "description")
LANGUAGES = [code for code, _ in settings.LANGUAGES]
DEFAULT_LANGUAGE = getattr(settings, "MODELTRANSLATION_DEFAULT_LANGUAGE", settings.LANGUAGE_CODE)


class Command(BaseCommand):
    help = "Import climate adaptation measures from a (multilingual) CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to the CSV file.")
        parser.add_argument(
            "--delimiter",
            default=",",
            help="CSV delimiter (default ','; use ';' for German Excel).",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        created, updated = 0, 0
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh, delimiter=options["delimiter"])
            fields = set(reader.fieldnames or [])
            self._check_header(fields)

            for i, row in enumerate(reader, start=2):  # row 1 is the header
                result = self._import_row(i, row)
                if result is None:
                    continue
                title, was_created = result
                created += was_created
                updated += not was_created
                self.stdout.write(f"{'Created' if was_created else 'Updated'}: {title}")

        self.stdout.write(self.style.SUCCESS(f"Done. {created} created, {updated} updated."))

    def _check_header(self, fields):
        missing = {"lat", "lng"} - fields
        if missing:
            raise CommandError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")
        title_cols = {"title"} | {f"title_{lang}" for lang in LANGUAGES}
        if not (title_cols & fields):
            raise CommandError("CSV needs a 'title' column (or title_da/title_de/title_en).")

    def _translated_values(self, row):
        """Return {field_lang: value} for every provided translated value."""
        values = {}
        for field in TRANSLATED_FIELDS:
            plain = (row.get(field) or "").strip()
            if plain:
                values[f"{field}_{DEFAULT_LANGUAGE}"] = plain
            for lang in LANGUAGES:
                val = (row.get(f"{field}_{lang}") or "").strip()
                if val:  # suffixed column wins over the plain one
                    values[f"{field}_{lang}"] = val
        return values

    def _resolve_slug(self, row, values):
        explicit = (row.get("slug") or "").strip()
        if explicit:
            return slugify(explicit)
        # Prefer English for a clean, stable, language-neutral slug (Danish/German
        # characters transliterate messily); then the default language; then any.
        for lang in ("en", DEFAULT_LANGUAGE, *LANGUAGES):
            val = values.get(f"title_{lang}")
            if val:
                return slugify(val)
        return ""

    def _import_row(self, i, row):
        try:
            lat = float(row["lat"])
            lng = float(row["lng"])
        except (TypeError, ValueError):
            self.stderr.write(f"Row {i}: invalid lat/lng, skipping.")
            return None

        values = self._translated_values(row)
        slug = self._resolve_slug(row, values)
        if not slug:
            self.stderr.write(f"Row {i}: no usable title/slug, skipping.")
            return None

        with transaction.atomic():
            defaults = {"lat": lat, "lng": lng, **values}
            measure, was_created = Measure.objects.update_or_create(slug=slug, defaults=defaults)
            self._set_tags(row, measure)
            self._add_images(i, row, measure)

        # A readable label for the console output.
        label = values.get(f"title_{DEFAULT_LANGUAGE}") or slug
        return label, was_created

    def _set_tags(self, row, measure):
        """Tags arrive in a single English column; slug from the English name."""
        names = [t.strip() for t in (row.get("tags") or "").split(";") if t.strip()]
        tags = []
        for name in names:
            tag, _ = Tag.objects.get_or_create(
                slug=slugify(name),
                # Seed the default-language name too so it is never blank.
                defaults={"name": name, "name_en": name},
            )
            if not tag.name_en:  # backfill for a pre-existing tag
                tag.name_en = name
                tag.save(update_fields=["name_en"])
            tags.append(tag)
        measure.tags.set(tags)

    def _add_images(self, i, row, measure):
        paths = [p.strip() for p in (row.get("image_paths") or "").split(";") if p.strip()]
        for j, img_path in enumerate(paths):
            path = Path(img_path)
            if not path.exists():
                self.stderr.write(f"Row {i} ({measure.slug}): image not found: {img_path}")
                continue
            if measure.pictures.filter(caption=path.name).exists():
                continue  # avoid re-importing the same file on re-runs
            with path.open("rb") as img_fh:
                pic = Picture(measure=measure, caption=path.name, is_preview=(j == 0), order=j)
                pic.image.save(path.name, File(img_fh), save=True)
