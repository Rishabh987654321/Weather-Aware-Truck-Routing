"""Serializers for routing and analysis API endpoints.

Handles request payload validation for POST /api/analyze:
- Coordinate ranges and equality checks
- Departure time window validation against forecast horizon
- Positive commercial truck load weights
- Valid checkpoint interval overrides
Source of truth: API.md, ARCHITECTURE.md sections 3 and 7, and Phase4.md.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from rest_framework import serializers

from risk.config import FORECAST_FUTURE_DAYS, FORECAST_PAST_DAYS


class LocationSerializer(serializers.Serializer):
    """Origin/destination coordinate pair with human-readable label."""

    lat = serializers.FloatField(
        min_value=-90.0,
        max_value=90.0,
        error_messages={
            "min_value": "Latitude must be between -90 and 90 degrees.",
            "max_value": "Latitude must be between -90 and 90 degrees.",
        },
    )
    lon = serializers.FloatField(
        min_value=-180.0,
        max_value=180.0,
        error_messages={
            "min_value": "Longitude must be between -180 and 180 degrees.",
            "max_value": "Longitude must be between -180 and 180 degrees.",
        },
    )
    label = serializers.CharField(required=False, allow_blank=True, default="")


class AnalyzeRequestSerializer(serializers.Serializer):
    """Validation serializer for POST /api/analyze requests."""

    origin = LocationSerializer()
    destination = LocationSerializer()
    departure_time = serializers.DateTimeField()
    load_lbs = serializers.FloatField(
        min_value=0.000001,
        error_messages={
            "min_value": "Cargo load (load_lbs) must be greater than 0.",
        },
    )
    checkpoint_interval_mi = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
    )

    def validate_departure_time(self, value: datetime) -> datetime:
        """Convert departure time to UTC and validate within forecast horizon."""
        if value.tzinfo is None:
            dep_utc = value.replace(tzinfo=timezone.utc)
        else:
            dep_utc = value.astimezone(timezone.utc)

        now_utc = datetime.now(timezone.utc)
        min_allowed = now_utc - timedelta(days=FORECAST_PAST_DAYS)
        max_allowed = now_utc + timedelta(days=FORECAST_FUTURE_DAYS)

        if dep_utc < min_allowed or dep_utc > max_allowed:
            min_str = min_allowed.strftime("%Y-%m-%dT%H:%M:%SZ")
            max_str = max_allowed.strftime("%Y-%m-%dT%H:%M:%SZ")
            dep_str = dep_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            raise serializers.ValidationError(
                f"Departure time {dep_str} is outside the allowed forecast window "
                f"({min_str} to {max_str})."
            )
        return dep_utc

    def validate_checkpoint_interval_mi(self, value: Optional[int]) -> Optional[int]:
        """Validate optional checkpoint spacing override."""
        if value is not None and value not in (10, 25, 50):
            raise serializers.ValidationError(
                "checkpoint_interval_mi must be one of 10, 25, 50 or null."
            )
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cross-field business rules: origin cannot equal destination."""
        origin = attrs.get("origin")
        destination = attrs.get("destination")
        if origin and destination:
            if (
                abs(origin["lat"] - destination["lat"]) < 1e-5
                and abs(origin["lon"] - destination["lon"]) < 1e-5
            ):
                raise serializers.ValidationError(
                    "Origin and destination cannot be the same location."
                )
        return attrs
