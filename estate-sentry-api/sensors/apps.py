from django.apps import AppConfig


class SensorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sensors'

    def ready(self):
        # Here and no earlier: discovery imports every handler module and checks
        # the types they claim against the Sensor model, which needs models
        # loaded. Fails loud — see sensors.registry.
        from .registry import HandlerRegistry

        HandlerRegistry.autodiscover()
