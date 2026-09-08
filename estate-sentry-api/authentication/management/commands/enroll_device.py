"""Enrol a trusted device from the command line.

This exists because of a bootstrapping problem that is otherwise unsolvable: a
`username` account authenticates *with* a device token, so it cannot log in to
enrol its first device. Somebody has to break the cycle from outside the API.

The command line is the right place for it on a self-hosted appliance — whoever
sets up a hallway tablet has shell access to the box it talks to, and shell
access is already a stronger credential than anything this would issue.

    python manage.py enroll_device kiosk "Hall tablet"
    python manage.py enroll_device kiosk "Hall tablet" --revoke-existing
"""

from django.core.management.base import BaseCommand, CommandError

from authentication.models import TrustedDevice, User


class Command(BaseCommand):
    help = "Enrol a trusted device for a user and print its token once."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("name", help='Device name, e.g. "Hall tablet"')
        parser.add_argument(
            "--revoke-existing",
            action="store_true",
            help="Revoke this user's other devices first (use when replacing a lost one)",
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist:
            raise CommandError(f"No user named {options['username']!r}.") from None

        if options["revoke_existing"]:
            revoked = 0
            for device in user.trusted_devices.filter(revoked_at__isnull=True):
                device.revoke()
                revoked += 1
            if revoked:
                self.stdout.write(f"Revoked {revoked} existing device(s).")

        device, raw_token = TrustedDevice.issue(user, options["name"])

        self.stdout.write(self.style.SUCCESS(f"\nEnrolled {device.name!r} for {user.username}."))
        self.stdout.write(f"\n  device id:    {device.id}")
        self.stdout.write(f"  device token: {raw_token}\n")
        self.stdout.write(
            "\nStore this token on the device now. Only its hash is kept here, so "
            "it cannot be shown again.\n"
        )

        if user.auth_method != "username":
            # Enrolling is still valid — it just will not be consulted, and
            # silently doing nothing useful is worth warning about.
            self.stdout.write(
                self.style.WARNING(
                    f"Note: {user.username} uses '{user.auth_method}' authentication, "
                    "so this token will not be used at login. Set auth_method to "
                    "'username' for a device-authenticated account."
                )
            )
