"""Zone model and API behaviour."""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from sensors.models import Sensor

from .models import Zone, ZonePerimeter, ZoneRule

User = get_user_model()

SQUARE = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]


class ActiveHoursTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="x")

    def zone(self, **kwargs):
        return Zone.objects.create(
            owner=self.user, name="Front Path", zone_type=Zone.ZoneType.ENTRY, **kwargs
        )

    def test_unset_hours_report_unknown_rather_than_false(self):
        """The distinction the rules engine depends on. If "no schedule" were
        reported as "outside active hours", a zone nobody configured would turn
        every single detection into an after-hours alert."""
        self.assertIsNone(self.zone().is_within_active_hours(datetime.time(3, 0)))

    def test_a_normal_window(self):
        zone = self.zone(
            active_hours_start=datetime.time(8, 0),
            active_hours_end=datetime.time(20, 0),
        )
        self.assertTrue(zone.is_within_active_hours(datetime.time(12, 0)))
        self.assertFalse(zone.is_within_active_hours(datetime.time(23, 0)))

    def test_a_window_that_wraps_past_midnight(self):
        """22:00-06:00 is the common case for a perimeter zone, and the one a
        naive start <= t <= end comparison gets exactly backwards."""
        zone = self.zone(
            active_hours_start=datetime.time(22, 0),
            active_hours_end=datetime.time(6, 0),
        )
        self.assertTrue(zone.is_within_active_hours(datetime.time(23, 30)))
        self.assertTrue(zone.is_within_active_hours(datetime.time(2, 0)))
        self.assertFalse(zone.is_within_active_hours(datetime.time(12, 0)))


class ZoneApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="x")
        self.other = User.objects.create_user(username="stranger", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.camera = Sensor.objects.create(
            name="passageway", sensor_type="CAMERA", location="side", owner=self.user
        )

    def create_zone(self, owner=None):
        return Zone.objects.create(
            owner=owner or self.user, name="Front Path", zone_type=Zone.ZoneType.ENTRY
        )

    def test_zone_creation_assigns_the_requesting_user(self):
        response = self.client.post(
            "/api/zones/", {"name": "Drive", "zone_type": "PERIMETER"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Zone.objects.get(name="Drive").owner, self.user)

    def test_zones_are_scoped_to_their_owner(self):
        self.create_zone(owner=self.other)
        response = self.client.get("/api/zones/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_perimeters_are_returned_with_the_zone(self):
        """The perception service reads zones and perimeters in one call at
        startup, so they must arrive together."""
        zone = self.create_zone()
        ZonePerimeter.objects.create(zone=zone, camera=self.camera, polygon=SQUARE)

        payload = self.client.get("/api/zones/").json()["results"][0]
        self.assertEqual(len(payload["perimeters"]), 1)
        self.assertEqual(payload["perimeters"][0]["polygon"], SQUARE)
        self.assertEqual(payload["perimeters"][0]["camera_name"], "passageway")

    def test_a_perimeter_can_be_posted_to_a_zone(self):
        zone = self.create_zone()
        response = self.client.post(
            f"/api/zones/{zone.id}/perimeters/",
            {"camera": self.camera.id, "polygon": SQUARE},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(zone.perimeters.count(), 1)

    def test_pixel_coordinates_are_rejected(self):
        """A polygon in pixels silently matches nothing, which looks like a quiet
        pipeline rather than a bad shape. Better to refuse it at the door."""
        zone = self.create_zone()
        response = self.client.post(
            f"/api/zones/{zone.id}/perimeters/",
            {"camera": self.camera.id, "polygon": [[100, 200], [400, 200], [400, 500]]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_a_polygon_needs_three_points(self):
        zone = self.create_zone()
        response = self.client.post(
            f"/api/zones/{zone.id}/perimeters/",
            {"camera": self.camera.id, "polygon": [[0.1, 0.1], [0.2, 0.2]]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rules_can_be_attached(self):
        zone = self.create_zone()
        response = self.client.post(
            f"/api/zones/{zone.id}/rules/",
            {
                "rule_type": ZoneRule.RuleType.ALERT_DWELL_TIME,
                "parameters": {"dwell_threshold_seconds": 30},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(zone.rules.count(), 1)

    def test_anonymous_access_is_refused(self):
        client = APIClient()
        self.assertIn(client.get("/api/zones/").status_code, (401, 403))


class SensorZoneLinkTests(TestCase):
    def test_deleting_a_zone_keeps_the_sensor(self):
        """SET_NULL, not CASCADE: unmapping a place must not delete the hardware
        record, or a mapping mistake becomes data loss."""
        user = User.objects.create_user(username="owner", password="x")
        zone = Zone.objects.create(
            owner=user, name="Front Path", zone_type=Zone.ZoneType.ENTRY
        )
        sensor = Sensor.objects.create(
            name="passageway", sensor_type="CAMERA", location="side",
            owner=user, zone=zone,
        )
        zone.delete()
        sensor.refresh_from_db()
        self.assertIsNone(sensor.zone)
