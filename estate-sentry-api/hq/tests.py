"""Tests for the HQ dashboard.

Focused on the parts with actual logic. The streaming endpoints themselves are
verified by running them (see the perception service README); what is worth
pinning here is the SSE rendering, because it builds HTML out of data that
arrived over the message bus.
"""

import json
import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from hq.views import _sse, known_cameras
from sensors.models import Sensor
from zones.models import Zone, ZonePerimeter


def event_payload(**overrides):
    payload = {
        "camera_id": "passageway",
        "frame_path": "frames/passageway/2026-09-04/x.jpg",
        "captured_at": "2026-09-04T22:15:31.123456+00:00",
        "motion": True,
        "motion_reason": "differenced",
        "detections": [
            {"label": "person", "category": "person", "confidence": 0.94,
             "box": [1, 2, 3, 4]},
        ],
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


class SseRenderingTests(TestCase):
    def test_renders_a_detection_as_an_sse_event(self):
        frame = _sse(7, event_payload()).decode()
        self.assertIn("id: 7\n", frame)
        self.assertIn("event: detection\n", frame)
        self.assertIn("passageway", frame)
        self.assertIn("person", frame)
        self.assertIn("94%", frame)

    def test_frame_is_terminated_and_single_line(self):
        """SSE is newline-delimited, so a stray newline inside `data:` would
        truncate the frame and the client would receive broken markup."""
        frame = _sse(1, event_payload()).decode()
        self.assertTrue(frame.endswith("\n\n"))
        data_lines = [ln for ln in frame.split("\n") if ln.startswith("data: ")]
        self.assertEqual(len(data_lines), 1)

    def test_category_drives_the_chip_class(self):
        frame = _sse(1, event_payload(detections=[
            {"label": "car", "category": "vehicle", "confidence": 0.8, "box": []},
        ])).decode()
        self.assertIn("chip--vehicle", frame)

    def test_motion_without_classification_is_still_reported(self):
        """A frame that passed the gate but classified as nothing is information,
        not an absence of it — something moved and the detector disagreed."""
        frame = _sse(1, event_payload(detections=[])).decode()
        self.assertIn("chip--none", frame)
        self.assertIn("nothing classified", frame)

    def test_hostile_values_are_escaped(self):
        """camera_id and labels arrive over the bus. Anything that can publish a
        frame notification could otherwise inject markup into every dashboard
        watching, so this is the boundary that has to hold."""
        frame = _sse(1, event_payload(
            camera_id='<img src=x onerror="alert(1)">',
            detections=[{"label": "<script>bad()</script>", "category": "person",
                         "confidence": 0.5, "box": []}],
        )).decode()

        # The property that matters is that hostile input cannot introduce a tag
        # or escape an attribute — not that its characters vanish. `onerror=`
        # surviving as literal text inside an escaped string is inert and fine.
        self.assertNotIn("<img", frame)
        self.assertNotIn("<script", frame)
        self.assertIn("&lt;script&gt;", frame)
        self.assertIn("&quot;", frame)

        # Stated directly: the only tags in the rendered fragment are the ones
        # this module writes. Anything else means the payload broke out.
        data = frame.split("data: ", 1)[1]
        tags = {m.lower() for m in re.findall(r"</?([a-zA-Z][a-zA-Z0-9]*)", data)}
        self.assertEqual(tags, {"li", "span", "em"})

    def test_malformed_payload_yields_nothing_rather_than_raising(self):
        """One bad message must not tear down every connected viewer's stream."""
        self.assertEqual(_sse(1, b"not json at all"), b"")

    def test_wrong_types_are_discarded_not_raised(self):
        """Everything here arrives over the bus, so a wrong type is as likely as
        malformed JSON. Either way the blast radius must stay at one message."""
        bad_confidence = event_payload(detections=[
            {"label": "person", "category": "person", "confidence": "high", "box": []},
        ])
        self.assertEqual(_sse(1, bad_confidence), b"")

        self.assertEqual(_sse(1, json.dumps({"detections": "not-a-list"}).encode()), b"")
        self.assertEqual(_sse(1, json.dumps([1, 2, 3]).encode()), b"")


class DashboardTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_dashboard_renders_a_tile_per_camera(self):
        response = self.client.get("/hq/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for camera in known_cameras():
            self.assertIn(camera, body)

    def test_cameras_come_from_registered_sensors(self):
        user = get_user_model().objects.create_user(username="zoner", password="x")
        Sensor.objects.create(
            name="side_gate", sensor_type="CAMERA", location="side", owner=user
        )
        Sensor.objects.create(
            name="hall_pir", sensor_type="MOTION", location="hall", owner=user
        )
        self.assertEqual(known_cameras(), ["side_gate"], "only CAMERA sensors")

    def test_a_registered_camera_becomes_streamable(self):
        """The name is the bus subject segment, so this list is also the
        allow-list for which streams may be opened."""
        user = get_user_model().objects.create_user(username="zoner2", password="x")
        Sensor.objects.create(
            name="side_gate", sensor_type="CAMERA", location="side", owner=user
        )
        self.assertEqual(self.client.get("/hq/cameras/nope/mjpeg").status_code, 400)

    def test_streams_are_deferred_until_page_load(self):
        """Held in data-src on purpose: an MJPEG connection never completes, so
        binding it to src keeps the document loading forever."""
        body = self.client.get("/hq/").content.decode()
        self.assertIn("data-src=", body)
        self.assertNotIn('<img class="camera__view"\n             src=', body)

    def test_zone_geometry_is_embedded_for_the_overlay(self):
        """Passed with the page rather than fetched: the dashboard holds no API
        credentials, so a separate endpoint would need its own auth story for
        data this view already has."""
        user = get_user_model().objects.create_user(username="zg", password="x")
        camera = Sensor.objects.create(
            name="passageway", sensor_type="CAMERA", location="side", owner=user
        )
        zone = Zone.objects.create(
            owner=user, name="Walkway", zone_type=Zone.ZoneType.HALLWAY
        )
        ZonePerimeter.objects.create(
            zone=zone, camera=camera,
            polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        )

        body = self.client.get("/hq/").content.decode()
        self.assertIn('id="camera-zones"', body)
        payload = json.loads(
            body.split('id="camera-zones" type="application/json">')[1].split("</script>")[0]
            .replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
        )
        self.assertIn("passageway", payload)
        self.assertEqual(payload["passageway"][0]["name"], "Walkway")
        self.assertEqual(len(payload["passageway"][0]["polygon"]), 4)

    def test_a_zone_name_cannot_break_out_of_the_json_script_tag(self):
        """Zone names are user-supplied and land inside a <script> block. Without
        escaping, a name containing a closing tag would end the block early and
        everything after it would be parsed as markup."""
        user = get_user_model().objects.create_user(username="zx", password="x")
        camera = Sensor.objects.create(
            name="passageway", sensor_type="CAMERA", location="s", owner=user
        )
        zone = Zone.objects.create(
            owner=user, name='</script><img src=x onerror=alert(1)>',
            zone_type=Zone.ZoneType.HALLWAY,
        )
        ZonePerimeter.objects.create(
            zone=zone, camera=camera, polygon=[[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]
        )

        body = self.client.get("/hq/").content.decode()
        block = body.split('id="camera-zones" type="application/json">')[1].split("</script>")[0]
        self.assertNotIn("</script", block)
        self.assertNotIn("<img", block)
        self.assertIn("\\u003c", block)

    def test_unknown_camera_is_rejected(self):
        """The camera id lands in a bus subject, so it must not be free-form."""
        response = self.client.get("/hq/cameras/..%2Fetc%2Fpasswd/mjpeg")
        self.assertIn(response.status_code, (400, 404))
