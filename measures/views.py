import json

from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from .models import Measure, Tag


def measure_to_dict(measure):
    """Serialise a measure for the client-side map + table."""
    preview = measure.preview_picture()
    return {
        "slug": measure.slug,
        "title": measure.title,
        "summary": measure.summary,
        "lat": measure.lat,
        "lng": measure.lng,
        # slug = language-neutral filter key; name = active-language label.
        "tags": [
            {"slug": t.slug, "name": t.name, "category": t.category, "color": t.color}
            for t in measure.tags.all()
        ],
        "preview_url": preview.image.url if preview else "",
        "detail_url": measure.get_absolute_url(),
    }


def measure_map(request):
    """Home page: map + tag filter + table, all driven by one JSON dataset."""
    measures = (
        Measure.objects.prefetch_related("tags", "pictures").all()
    )
    data = [measure_to_dict(m) for m in measures]
    # num_measures lets the template grey out tags that no measure uses.
    tags = Tag.objects.annotate(num_measures=Count("measures"))
    # Group tags into separate filter sections (Type / Goal / Source / Other).
    labels = dict(Tag.Category.choices)
    tag_groups = []
    for category in ("kind", "goal", "source", "other"):
        group_tags = [t for t in tags if t.category == category]
        if group_tags:
            tag_groups.append({"category": category, "label": labels[category], "tags": group_tags})
    context = {
        "measures_json": json.dumps(data),
        "tag_groups": tag_groups,
        "measure_count": len(data),
    }
    return render(request, "measures/map.html", context)


def measure_detail(request, slug):
    measure = get_object_or_404(
        Measure.objects.prefetch_related("tags", "pictures"), slug=slug
    )
    return render(request, "measures/measure_detail.html", {"measure": measure})
