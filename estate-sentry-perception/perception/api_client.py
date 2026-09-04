"""Client for the Django API.

The perception service reads zone perimeters from the API at startup and writes
zone events back to it. It does not touch the database directly: the API owns
the schema, and a second writer with its own idea of the models is how those two
drift apart.

Failures here are deliberately non-fatal. If the API is down the pipeline keeps
detecting and simply cannot attribute detections to zones — degraded, but a
camera that still sees is worth more than one that stopped because a web service
restarted.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from .pipeline.zones import Perimeter, ZoneIndex

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0


class ApiClient:
    """Token-authenticated client for the zone and event endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.environ.get("API_URL", "http://localhost:8000")).rstrip("/")
        self.token = token or os.environ.get("PERCEPTION_API_TOKEN", "")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Token {self.token}"} if self.token else {},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @property
    def configured(self) -> bool:
        """Whether a token was supplied.

        Without one the API rejects every request, so it is worth saying so once
        at startup rather than emitting an authentication failure per frame.
        """
        return bool(self.token)

    async def fetch_zone_index(self) -> ZoneIndex:
        """Build the perimeter index from `/api/zones/`.

        Returns an empty index on failure rather than raising. An empty index
        means detections are not attributed to zones, which the caller reports
        clearly — that is a better outcome than refusing to start.
        """
        try:
            zones = await self._get_all("/api/zones/")
        except (httpx.HTTPError, ValueError):
            logger.warning("could not fetch zones; continuing without them", exc_info=True)
            return ZoneIndex()

        perimeters: list[Perimeter] = []

        for zone in zones:
            for perimeter in zone.get("perimeters") or []:
                polygon = [tuple(pt) for pt in perimeter.get("polygon") or []]
                if len(polygon) < 3:
                    logger.warning(
                        "zone %r has a perimeter with %d points; skipping",
                        zone.get("name"),
                        len(polygon),
                    )
                    continue
                perimeters.append(
                    Perimeter(
                        zone_id=str(zone["id"]),
                        zone_name=zone.get("name", "?"),
                        camera_pk=perimeter["camera"],
                        camera_name=perimeter.get("camera_name", ""),
                        polygon=polygon,
                    )
                )

        index = ZoneIndex(perimeters)
        logger.info(
            "loaded %d perimeter(s) across %d camera(s): %s",
            len(index),
            len(index.cameras),
            ", ".join(index.cameras) or "none",
        )
        return index

    async def _get_all(self, url: str) -> list[dict[str, Any]]:
        """Collect every page of a paginated list endpoint.

        The API paginates at 50 by default. Reading only the first page would
        work perfectly on a small install and then quietly stop attributing
        detections in whichever zones happened to sort last — the kind of bug
        that appears only once a deployment grows.
        """
        items: list[dict[str, Any]] = []
        next_url: str | None = url

        while next_url:
            response = await self._client.get(next_url)
            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, list):  # pagination disabled
                items.extend(payload)
                break

            items.extend(payload.get("results", []))
            next_url = payload.get("next")

        return items

    async def post_zone_events(self, events: list[dict[str, Any]]) -> int:
        """Append events to the log. Returns how many were accepted.

        Batched: the pipeline produces several detections per frame, and at a few
        frames per second a request each would spend more time on HTTP round
        trips than on inference.
        """
        if not events:
            return 0
        try:
            response = await self._client.post(
                "/api/intelligence/zone-events/bulk/", json={"events": events}
            )
            response.raise_for_status()
            return int(response.json().get("created", 0))
        except (httpx.HTTPError, ValueError):
            # Losing a log write must not lose the frame. Reported, not raised.
            logger.warning("could not write %d zone event(s)", len(events), exc_info=True)
            return 0
