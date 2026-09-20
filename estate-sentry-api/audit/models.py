"""The security audit log.

Append-only, following the precedent `intelligence.ZoneEvent` sets: it is
evidence, written once. There is no update or delete route, and `save()` refuses
to rewrite an existing row, so an entry cannot be quietly amended after the fact
by anything — including a future bug.
"""

from django.conf import settings
from django.db import models

from core.validators import for_field


class AuditLogQuerySet(models.QuerySet):
    """Refuses the bulk operations that would bypass the model's guarantees.

    `Model.save()` and `Model.delete()` are not enough on their own:
    `QuerySet.update()` and `QuerySet.delete()` go straight to SQL without
    touching either, so an append-only model with only instance-level guards is
    append-only by convention. This makes it structural.

    Cascade handling is unaffected — Django's deletion collector issues its own
    `sql.UpdateQuery` for `SET_NULL` rather than calling `QuerySet.update()`, so
    deleting an actor still nulls the reference.
    """

    def delete(self):
        raise ValueError('Audit entries are append-only; they cannot be deleted.')

    def update(self, **kwargs):
        raise ValueError('Audit entries are append-only; they cannot be updated.')


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('REGISTER', 'Account created'),
        ('USER_UPDATE', 'Account updated'),
        ('DEVICE_ENROL', 'Device enrolled'),
        ('DEVICE_REVOKE', 'Device revoked'),
        ('SENSOR_CREATE', 'Sensor created'),
        ('SENSOR_UPDATE', 'Sensor updated'),
        ('SENSOR_DELETE', 'Sensor deleted'),
        ('ALERT_ACKNOWLEDGE', 'Alert acknowledged'),
        ('ZONE_CREATE', 'Zone created'),
        ('ZONE_UPDATE', 'Zone updated'),
        ('ZONE_DELETE', 'Zone deleted'),
    ]

    OUTCOME_CHOICES = [
        ('SUCCESS', 'Success'),
        ('DENIED', 'Denied'),     # authenticated but not permitted, or refused
        ('FAILURE', 'Failure'),   # rejected, malformed, or errored
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # SET_NULL, not CASCADE: deleting an account must not delete the record of
    # what it did. `actor_username` is denormalised for the same reason — it is
    # the only thing that still names the actor once the row is gone.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_entries',
    )
    actor_username = models.CharField(max_length=150, blank=True)

    action = models.CharField(max_length=40, choices=ACTION_CHOICES, db_index=True)
    outcome = models.CharField(max_length=10, choices=OUTCOME_CHOICES)

    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=64, blank=True)

    method = models.CharField(max_length=10)
    path = models.CharField(max_length=512)
    status_code = models.PositiveSmallIntegerField()

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    metadata = models.JSONField(
        default=dict,
        validators=for_field('audit.metadata'),
        help_text='Additional context recorded by the view',
    )

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        db_table = 'audit_log'
        verbose_name = 'Audit entry'
        verbose_name_plural = 'Audit entries'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['actor', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['outcome', '-timestamp']),
        ]

    def __str__(self):
        who = self.actor_username or 'anonymous'
        return f'{self.timestamp:%Y-%m-%d %H:%M:%S} {who} {self.action} {self.outcome}'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError(
                'Audit entries are append-only; an existing entry cannot be '
                'modified.'
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit entries are append-only; they cannot be deleted.')
