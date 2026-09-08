"""Dashboard views.

Two of these are long-lived streaming responses, which is the whole reason the
HQ runs under ASGI. Under WSGI each open stream occupies a worker for as long as
someone is watching, so three viewers would exhaust the default pool and the API
would stop answering. As async views they are cheap.
"""

from __future__ import annotations

import asyncio
import json
import logging

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    StreamingHttpResponse,
)
from django.shortcuts import render

from perception.ring import TooManySubscribers

from sensors.models import Sensor
from zones.models import ZonePerimeter

from .live import bridge

logger = logging.getLogger(__name__)

MJPEG_BOUNDARY = "estatesentryframe"

#: Fallback when no CAMERA sensors are registered — a fresh install would
#: otherwise render an empty page with no hint that anything is missing.
FALLBACK_CAMERAS = ["passageway", "driveway", "front_door"]


def known_cameras() -> list[str]:
    """Camera names from the database.

    The name is what identifies a camera on the wire: it is the `camera_id` in
    `frames.{camera_id}.raw` and the key the perception service matches
    perimeters against. So this list also decides which stream URLs are
    accepted, which is why the MJPEG view checks against it rather than passing
    a path segment through to a bus subject.
    """
    return list(_camera_names_queryset()) or FALLBACK_CAMERAS


def _camera_names_queryset():
    return (
        Sensor.objects.filter(sensor_type="CAMERA")
        .order_by("name")
        .values_list("name", flat=True)
    )


async def aknown_cameras() -> list[str]:
    """Async twin of `known_cameras`, for the streaming views.

    Django refuses synchronous ORM calls from an async context, and rightly so:
    a blocking query inside an async view stalls the event loop, and with it
    every other viewer's stream.
    """
    names = [name async for name in _camera_names_queryset()]
    return names or FALLBACK_CAMERAS


def camera_zones() -> dict[str, list[dict]]:
    """Zone perimeters per camera, ready to draw.

    Passed into the page rather than fetched by the browser. The perimeters are
    already loaded to render this view, the payload is a few hundred bytes, and
    an extra endpoint would need its own authentication story — the API requires
    a token the dashboard does not have.
    """
    perimeters = (
        ZonePerimeter.objects.select_related("zone", "camera")
        .order_by("zone__name")
    )
    by_camera: dict[str, list[dict]] = {}
    for perimeter in perimeters:
        by_camera.setdefault(perimeter.camera.name, []).append(
            {
                "name": perimeter.zone.name,
                "type": perimeter.zone.zone_type,
                "polygon": perimeter.polygon,
            }
        )
    return by_camera


def dashboard(request: HttpRequest) -> HttpResponse:
    cameras = known_cameras()
    return render(
        request,
        "hq/dashboard.html",
        {
            "cameras": cameras,
            "using_fallback": cameras is FALLBACK_CAMERAS or cameras == FALLBACK_CAMERAS,
            "camera_zones": camera_zones(),
        },
    )


async def camera_mjpeg(request: HttpRequest, camera_id: str) -> HttpResponse:
    """Live camera as `multipart/x-mixed-replace`.

    Consumed by a plain `<img src="...">`, so the live view needs no JavaScript
    at all — the browser replaces the image as each part arrives.
    """
    if camera_id not in await aknown_cameras():
        return HttpResponseBadRequest("unknown camera")

    async def frames():
        try:
            async with bridge.feed(camera_id).viewer() as sub:
                async for entry in sub:
                    yield (
                        f"--{MJPEG_BOUNDARY}\r\n"
                        f"Content-Type: image/jpeg\r\n"
                        f"Content-Length: {len(entry.item)}\r\n\r\n"
                    ).encode()
                    yield entry.item
                    yield b"\r\n"
        except TooManySubscribers:
            logger.warning("viewer limit reached for %s", camera_id)
        except asyncio.CancelledError:
            # Normal: the viewer navigated away or closed the tab.
            raise

    response = StreamingHttpResponse(
        frames(),
        content_type=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
    )
    # Proxies that buffer would defeat the point of a live stream.
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["X-Accel-Buffering"] = "no"
    return response


async def events_stream(request: HttpRequest) -> HttpResponse:
    """Detection events as SSE, consumed by htmx's sse extension.

    Honours `Last-Event-ID` (which EventSource resends automatically on
    reconnect) so a client that dropped receives only what it missed, rather
    than a replay of the whole buffer.
    """
    try:
        since_id = int(request.headers.get("Last-Event-ID") or request.GET.get("since_id") or 0)
    except ValueError:
        since_id = 0

    async def stream():
        # Tell the browser how long to wait before reconnecting, then replay the
        # gap before attaching live, so nothing falls between the two.
        yield b"retry: 3000\n\n"
        for entry in bridge.event_history(since_id=since_id or None):
            yield _sse(entry.id, entry.item)

        last_seen = since_id
        async with bridge.events() as sub:
            while True:
                try:
                    entry = await asyncio.wait_for(sub.get(), timeout=15)
                except TimeoutError:
                    # A comment frame. Keeps proxies and load balancers from
                    # closing an idle connection, and lets the client tell
                    # "quiet" from "disconnected".
                    yield b": keep-alive\n\n"
                    continue
                if entry.id <= last_seen:
                    continue
                last_seen = entry.id
                yield _sse(entry.id, entry.item)
                # Geometry rides on its own event. htmx swaps the HTML one into
                # the feed; the overlay is drawn by hand from this one, because
                # positioning boxes over a scaled video is not a swap.
                yield _sse_boxes(entry.id, entry.item)

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["X-Accel-Buffering"] = "no"
    return response


def _sse(event_id: int, payload: bytes) -> bytes:
    """Render one detection as an SSE `detection` event carrying an HTML fragment.

    htmx swaps HTML, not JSON, so the fragment is built here. Doing it server-side
    is the point of the approach: there is no client-side template to keep in
    sync with the model.
    """
    # The whole render is guarded, not just the parse. Everything here comes off
    # the bus, so a wrong *type* is as likely as malformed JSON — a non-numeric
    # confidence would otherwise raise out of this function and kill the stream
    # for every connected viewer, which is a large blast radius for one bad
    # message.
    try:
        event = json.loads(payload)
        detections = event.get("detections") or []
        camera = _escape(str(event.get("camera_id", "?")))
        when = _escape(str(event.get("captured_at", ""))[11:19])

        if detections:
            chips = "".join(
                f'<span class="chip chip--{_escape(str(d.get("category", "unknown")))}">'
                f'{_escape(str(d.get("label", "?")))}'
                f'<em>{float(d.get("confidence", 0)):.0%}</em></span>'
                for d in detections
            )
        else:
            chips = '<span class="chip chip--none">motion, nothing classified</span>'
    except (ValueError, TypeError, AttributeError):
        logger.warning("discarding an unrenderable detection event", exc_info=True)
        return b""

    html = (
        f'<li class="event"><span class="event__cam">{camera}</span>'
        f'<span class="event__time">{when}</span>'
        f'<span class="event__chips">{chips}</span></li>'
    )
    # SSE frames are newline-delimited, so the payload must not contain any.
    return f"id: {event_id}\nevent: detection\ndata: {html}\n\n".encode()


def _sse_boxes(event_id: int, payload: bytes) -> bytes:
    """Render one frame's detections as a `boxes` event carrying JSON geometry.

    Boxes are normalised to 0-1 here rather than on the client. The dashboard
    scales the stream to fit its tile and has no idea of the source resolution,
    so pixel coordinates would be meaningless by the time they arrived.
    """
    try:
        event = json.loads(payload)
        width = float(event.get("frame_width") or 0)
        height = float(event.get("frame_height") or 0)
        if width <= 0 or height <= 0:
            # Older events, or a producer that did not report dimensions. Skip
            # rather than guess: a box drawn at the wrong scale is worse than
            # no box, because it looks authoritative.
            return b""

        zones = event.get("zones") or []
        boxes = []
        for i, detection in enumerate(event.get("detections") or []):
            x1, y1, x2, y2 = (float(v) for v in detection["box"])
            boxes.append(
                {
                    "x": round(x1 / width, 5),
                    "y": round(y1 / height, 5),
                    "w": round((x2 - x1) / width, 5),
                    "h": round((y2 - y1) / height, 5),
                    "label": str(detection.get("label", "?")),
                    "category": str(detection.get("category", "unknown")),
                    "confidence": float(detection.get("confidence", 0)),
                    "zones": zones[i] if i < len(zones) else [],
                }
            )
        data = json.dumps({"camera": event.get("camera_id"), "boxes": boxes})
    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
        logger.warning("discarding unrenderable box geometry", exc_info=True)
        return b""

    return f"id: {event_id}\nevent: boxes\ndata: {data}\n\n".encode()


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
