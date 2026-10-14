from django.urls import path

from .views import analyze_view, geocode_view, health_check, heatmap_view

urlpatterns = [
    path("health", health_check, name="health-check"),
    path("health/", health_check, name="health-check-slash"),
    path("geocode", geocode_view, name="geocode"),
    path("geocode/", geocode_view, name="geocode-slash"),
    path("analyze", analyze_view, name="analyze"),
    path("analyze/", analyze_view, name="analyze-slash"),
    path("heatmap", heatmap_view, name="heatmap"),
    path("heatmap/", heatmap_view, name="heatmap-slash"),
]
