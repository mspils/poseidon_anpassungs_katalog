"""Import the Poseidon cases (German + Danish source rows) from a CSV.

Usage:
    python manage.py import_poseidon [poseidon_merged.csv] [--clear]

CSV columns:
    id, name_de, name_dk, location, coordinates, country, code,
    goal_de, goal_dk, description_de, description_dk

  * _de -> German fields, _dk -> Danish (da) fields.
  * coordinates : "55.45711°, 10.40135°"  -> lat, lng
  * code        : "<kinds>-<source>", e.g. "NT-M". The kind part is one or
                  more letters (N/T/D/S); the source part is one letter (M/S).
                  Each letter maps to a tag (see CODE_KINDS / CODE_SOURCES).

English fields are left empty and fall back to Danish. Tags carry real da/de/en
names. Idempotent on the measure slug (derived from the German name), so
re-running updates rather than duplicating.
"""

import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from measures.models import Measure, Tag

# kind letter -> tag. category "kind"; colour drives the map markers.
CODE_KINDS = {
    "N": dict(slug="nature-based", color="#2E7D32",
              da="Naturbaserede og naturinspirerede løsninger",
              de="Naturbasierte und von der Natur inspirierte Lösungen",
              en="Nature-based and nature-inspired solutions"),
    "T": dict(slug="technical", color="#2660A4",
              da="Tekniske løsninger", de="Technische Lösungen", en="Technical solutions"),
    "D": dict(slug="digital", color="#E8A33D",
              da="Digitale løsninger", de="Digitale Lösungen", en="Digital solutions"),
    "S": dict(slug="cooperative", color="#7E57C2",
              da="Samarbejdsbaserede løsninger", de="Kooperative Lösungen", en="Cooperative solutions"),
}
# source letter -> tag. category "source"; no colour.
CODE_SOURCES = {
    "S": dict(slug="survey", color="", da="Spørgeundersøgelse", de="Umfrage", en="Survey"),
    "M": dict(slug="manual", color="", da="Manuel", de="Manuell", en="Manual"),
}


class Command(BaseCommand):
    help = "Import the Poseidon example cases from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", nargs="?", default="poseidon_merged.csv")
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete all existing measures before importing.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        if options["clear"]:
            deleted, _ = Measure.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared existing measures ({deleted} rows)."))

        created, updated = 0, 0
        with csv_path.open(newline="", encoding="utf-8-sig") as fh:
            for i, row in enumerate(csv.DictReader(fh), start=2):
                result = self._import_row(i, row)
                if result is None:
                    continue
                created += result
                updated += not result

        self.stdout.write(self.style.SUCCESS(f"Done. {created} created, {updated} updated."))

    def _parse_coords(self, raw):
        nums = re.findall(r"-?\d+\.?\d*", raw or "")
        if len(nums) < 2:
            return None
        return float(nums[0]), float(nums[1])

    def _tags_from_code(self, code):
        """'NT-M' -> [nature-based, technical, manual] (as Tag objects)."""
        code = (code or "").strip().upper()
        kinds, _, source = code.partition("-")
        specs = [(CODE_KINDS[c], "kind") for c in kinds if c in CODE_KINDS]
        if source in CODE_SOURCES:
            specs.append((CODE_SOURCES[source], "source"))
        tags = []
        for spec, category in specs:
            tag, _created = Tag.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["da"], "name_da": spec["da"],
                    "name_de": spec["de"], "name_en": spec["en"],
                    "category": category, "color": spec["color"],
                },
            )
            tags.append(tag)
        return tags

    def _import_row(self, i, row):
        name_de = (row.get("name_de") or "").strip()
        name_dk = (row.get("name_dk") or "").strip()
        if not (name_de or name_dk):
            self.stderr.write(f"Row {i}: empty name, skipping.")
            return None
        coords = self._parse_coords(row.get("coordinates"))
        if coords is None:
            self.stderr.write(f"Row {i} ({name_de or name_dk}): unparseable coordinates, skipping.")
            return None
        lat, lng = coords

        # Fold the human-readable region/country into both descriptions.
        location = ", ".join(p for p in [(row.get("location") or "").strip(),
                                         (row.get("country") or "").strip()] if p)
        desc_de = self._with_location((row.get("description_de") or "").strip(), location)
        desc_dk = self._with_location((row.get("description_dk") or "").strip(), location)
        goal_de = self._clip((row.get("goal_de") or "").strip())
        goal_dk = self._clip((row.get("goal_dk") or "").strip())

        with transaction.atomic():
            measure, was_created = Measure.objects.update_or_create(
                # Slug from the German name (stable, language-neutral key).
                slug=slugify(name_de or name_dk),
                defaults={
                    "lat": lat, "lng": lng,
                    "title_de": name_de, "title_da": name_dk,
                    "summary_de": goal_de, "summary_da": goal_dk,
                    "description_de": desc_de, "description_da": desc_dk,
                },
            )
            measure.tags.set(self._tags_from_code(row.get("code")))

        self.stdout.write(f"{'Created' if was_created else 'Updated'}: {name_de or name_dk}")
        return was_created

    @staticmethod
    def _with_location(description, location):
        return f"{description}\n\n{location}".strip() if location else description

    @staticmethod
    def _clip(text, limit=300):
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
