from django.urls import path

from . import views

app_name = "measures"

urlpatterns = [
    path("", views.measure_map, name="map"),
    path("measure/<slug:slug>/", views.measure_detail, name="detail"),
]
