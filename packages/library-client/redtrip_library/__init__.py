"""Shanghai Library HTTP client for RedTrip (aligned with SLC MCP)."""

from .client import SlcClient, SlcResponse
from .osm import bbox_from_points, fetch_building_footprints

__all__ = [
    "SlcClient",
    "SlcResponse",
    "bbox_from_points",
    "fetch_building_footprints",
]
