"""URL configuration for the catalogue project."""

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# Language-neutral routes (no /<lang>/ prefix).
urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),  # set_language endpoint
]

# Language-prefixed routes: /da/, /de/, /en/ ...
urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("", include("measures.urls")),
)

# Serve uploaded media files during development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
