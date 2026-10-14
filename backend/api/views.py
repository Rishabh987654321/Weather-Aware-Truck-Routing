"""API views for geocoding, health check, and route risk analysis.

Source of truth: API.md, ARCHITECTURE.md sections 3 and 7, and Phase4.md.
"""

from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from api.serializers import AnalyzeRequestSerializer
from services.analysis import run_analyze_pipeline
from services.checkpoints import build_checkpoints, choose_interval
from services.corridor import generate_heatmap_data
from services.geocode import search_geocode
from services.osrm import NoRouteError, UpstreamError, fetch_routes


@api_view(["GET"])
def health_check(request):
    """Health check endpoint."""
    return Response({"status": "ok"})


class GeocodeRateThrottle(AnonRateThrottle):
    scope = "geocode"


class AnalyzeRateThrottle(AnonRateThrottle):
    scope = "analyze"


class HeatmapRateThrottle(AnonRateThrottle):
    scope = "heatmap"


@api_view(["GET"])
@throttle_classes([GeocodeRateThrottle])
def geocode_view(request):
    """Search for locations via Nominatim.

    GET /api/geocode?q=<text>
    Returns: {"results": [{"label": str, "lat": float, "lon": float}]}
    """
    query = request.query_params.get("q", "").strip()
    if len(query) < 2:
        return Response(
            {"error": "Query parameter 'q' must be at least 2 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    results = search_geocode(query)
    return Response({"results": results})


@api_view(["POST"])
@throttle_classes([AnalyzeRateThrottle])
def analyze_view(request):
    """Execute complete weather-aware truck routing pipeline.

    POST /api/analyze
    Returns contract defined in API.md.
    """
    serializer = AnalyzeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data
    try:
        result = run_analyze_pipeline(
            origin=validated_data["origin"],
            destination=validated_data["destination"],
            departure_time_utc=validated_data["departure_time"],
            load_lbs=validated_data["load_lbs"],
            checkpoint_interval_mi=validated_data.get("checkpoint_interval_mi"),
        )
        return Response(result, status=status.HTTP_200_OK)
    except NoRouteError as e:
        return Response(
            {"error": str(e) or "No drivable route found between origin and destination."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except UpstreamError as e:
        return Response(
            {"error": f"Upstream routing service failure: {e}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(["POST"])
@throttle_classes([HeatmapRateThrottle])
def heatmap_view(request):
    """Generate 49-hour corridor weather risk heatmap for trip alternatives.

    POST /api/heatmap
    Takes same parameters as analyze: origin, destination, departure_time, load_lbs.
    Returns: {"start_time": str, "hours": 49,
              "points": [{"lat": float, "lon": float, "intensity": [...]}]}
    """
    serializer = AnalyzeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data
    origin = validated_data["origin"]
    destination = validated_data["destination"]
    departure_time = validated_data["departure_time"]
    load_lbs = validated_data["load_lbs"]
    checkpoint_interval_mi = validated_data.get("checkpoint_interval_mi")

    try:
        orig_coords = (float(origin["lat"]), float(origin["lon"]))
        dest_coords = (float(destination["lat"]), float(destination["lon"]))

        # 1. Fetch routes from OSRM (reuses the 24h OSRM cache warmed by analyze)
        routes_data = fetch_routes(orig_coords, dest_coords)
        raw_routes = routes_data.get("routes", [])
        if not raw_routes:
            raise NoRouteError("No drivable route found between origin and destination.")

        # 2. Build checkpoints for each route (for shared weather cache window alignment)
        for rt in raw_routes:
            dist_mi = float(rt["distance_mi"])
            chosen_interval = choose_interval(dist_mi, override=checkpoint_interval_mi)
            cps = build_checkpoints(rt, chosen_interval, departure_time)
            rt["checkpoints"] = cps

        # 3. Generate heatmap grid and 49 hourly intensities
        heatmap_result = generate_heatmap_data(
            routes=raw_routes,
            departure_time_utc=departure_time,
            load_lbs=load_lbs,
        )
        return Response(heatmap_result, status=status.HTTP_200_OK)
    except NoRouteError as e:
        return Response(
            {"error": str(e) or "No drivable route found between origin and destination."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except UpstreamError as e:
        return Response(
            {"error": f"Upstream routing service failure: {e}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

