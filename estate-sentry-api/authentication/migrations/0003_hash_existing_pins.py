"""Hash any PIN still stored in plain text.

The `pin` column previously held the PIN itself. 0002 widened it to hold a hash;
this converts whatever is already there.

Runs one way only. A reverse would have to recover PINs from hashes, which is
precisely what the change exists to prevent — so reversing this migration leaves
the hashes in place, and affected users must set a new PIN. That is stated
rather than silently implied, because a `RunPython.noop` reverse looks like
"nothing to undo" when it really means "cannot be undone".
"""

from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations


def hash_plaintext_pins(apps, schema_editor):
    User = apps.get_model("authentication", "User")

    converted = 0
    for user in User.objects.exclude(pin__isnull=True).exclude(pin="").iterator():
        try:
            identify_hasher(user.pin)
        except ValueError:
            # Not a recognised hash, so it is the PIN itself. Distinguishing them
            # by format is reliable: a Django hash always carries its algorithm
            # as a prefix, and a four-digit PIN never will.
            user.pin = make_password(user.pin)
            user.save(update_fields=["pin"])
            converted += 1

    if converted:
        print(f"  hashed {converted} plaintext PIN(s)")


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0002_user_failed_auth_attempts_user_locked_until_and_more"),
    ]

    operations = [
        migrations.RunPython(hash_plaintext_pins, migrations.RunPython.noop),
    ]
