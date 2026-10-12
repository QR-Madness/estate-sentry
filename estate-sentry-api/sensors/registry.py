"""The sensor handler registry.

Maps each sensor type to the handler that understands its readings, and is the
API `docs/guides/plugin-development.md` describes. Three ways in:

1. **Discovery.** Any `BaseSensorHandler` subclass *defined* in a module of
   `sensors.handlers`, with a non-empty `SENSOR_TYPES`, is registered when the
   app starts (`SensorsConfig.ready()`). Classes merely imported into a module
   are not, and helpers with no `SENSOR_TYPES` are skipped.
2. **Explicitly**, with `HandlerRegistry.register_handler(MyHandler)`.
3. **Entry points.** An installed package advertises handlers in the
   `estate_sentry.handlers` group.

**Every failure is loud.** A handler that cannot be registered raises
`ImproperlyConfigured` at startup. The quiet alternative — skip it, and store
that type's readings unvalidated with no threat detection — is exactly the
failure this registry ends: before it, seven of ten sensor types had no handler,
and a smoke detector reporting smoke raised nothing.
"""

import importlib
import inspect
import pkgutil
from importlib.metadata import entry_points

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from jsonschema.exceptions import SchemaError

from .handlers.base import BaseSensorHandler, _compiled

ENTRY_POINT_GROUP = 'estate_sentry.handlers'


class HandlerRegistry:
    """Class-level, so plugins can call ``HandlerRegistry.register_handler()``."""

    #: sensor type -> handler class
    _handlers = {}

    # -- registration ---------------------------------------------------------

    @classmethod
    def register_handler(cls, handler_cls):
        """Register a handler for every type it names. Returns it, so it also
        works as a decorator. Re-registering the same class is a no-op."""
        cls._check(handler_cls)
        for sensor_type in handler_cls.SENSOR_TYPES:
            cls._handlers[sensor_type] = handler_cls
        return handler_cls

    @classmethod
    def unregister_handler(cls, handler_cls):
        for sensor_type in [t for t, h in cls._handlers.items() if h is handler_cls]:
            del cls._handlers[sensor_type]

    # -- lookup ---------------------------------------------------------------

    @classmethod
    def get_handler(cls, sensor_type):
        """The handler class for a type, or None — `CUSTOM` has none by design."""
        return cls._handlers.get(sensor_type)

    @classmethod
    def get_handler_for(cls, sensor):
        """A handler instance bound to `sensor`, or None."""
        handler_cls = cls.get_handler(sensor.sensor_type)
        return handler_cls(sensor) if handler_cls is not None else None

    @classmethod
    def registered_types(cls):
        return frozenset(cls._handlers)

    # -- discovery ------------------------------------------------------------

    @classmethod
    def autodiscover(cls):
        """Register this package's handlers, then installed plugins'. Idempotent."""
        cls._discover_package()
        cls._discover_entry_points()
        # Anything registered before models were ready — a plugin calling
        # register_handler() from its own __init__.py — is checked against the
        # model's sensor types now.
        for handler_cls in set(cls._handlers.values()):
            cls._check_sensor_types(handler_cls)

    @classmethod
    def _discover_package(cls):
        from . import handlers as package

        for info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f'{package.__name__}.{info.name}')
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseSensorHandler)
                    and obj is not BaseSensorHandler
                    and obj.__module__ == module.__name__
                    and obj.SENSOR_TYPES
                ):
                    cls.register_handler(obj)

    @classmethod
    def _discover_entry_points(cls):
        for ep in entry_points(group=ENTRY_POINT_GROUP):
            try:
                handler_cls = ep.load()
            except Exception as exc:
                raise ImproperlyConfigured(
                    f'Entry point {ep.name!r} ({ep.value}) in group '
                    f'{ENTRY_POINT_GROUP!r} failed to load: {exc}'
                ) from exc
            cls.register_handler(handler_cls)

    # -- checks ---------------------------------------------------------------

    @classmethod
    def _check(cls, handler_cls):
        name = getattr(handler_cls, '__qualname__', repr(handler_cls))

        if not (inspect.isclass(handler_cls) and issubclass(handler_cls, BaseSensorHandler)):
            raise ImproperlyConfigured(f'{name} is not a BaseSensorHandler subclass.')

        if inspect.isabstract(handler_cls):
            missing = ', '.join(sorted(handler_cls.__abstractmethods__))
            raise ImproperlyConfigured(f'{name} is abstract; it does not implement {missing}.')

        if not handler_cls.SENSOR_TYPES:
            raise ImproperlyConfigured(f'{name} declares no SENSOR_TYPES.')

        for sensor_type in handler_cls.SENSOR_TYPES:
            existing = cls._handlers.get(sensor_type)
            if existing is not None and existing is not handler_cls:
                # Ambiguous dispatch on a security system is worse than refusing
                # to start: whichever handler won, the other's detection would
                # silently never run.
                raise ImproperlyConfigured(
                    f'{sensor_type} is claimed by both {existing.__qualname__} and {name}.'
                )

        # A registered handler must validate *something*. One with no schema and
        # the default validate_reading would accept any payload at all.
        overrides_validation = handler_cls.validate_reading is not BaseSensorHandler.validate_reading
        if handler_cls.get_reading_schema() is None and not overrides_validation:
            raise ImproperlyConfigured(
                f'{name} validates nothing: declare get_reading_schema() or '
                f'override validate_reading().'
            )

        for kind in ('reading', 'connection'):
            try:
                _compiled(handler_cls, kind)
            except SchemaError as exc:
                raise ImproperlyConfigured(
                    f'{name} has a malformed {kind} schema: {exc.message}'
                ) from exc

        if apps.models_ready:
            cls._check_sensor_types(handler_cls)

    @classmethod
    def _check_sensor_types(cls, handler_cls):
        """A type the model cannot hold makes the handler dead code — almost
        always a typo, and one that would otherwise fail without a sound."""
        from .models import Sensor

        known = {choice for choice, _ in Sensor.SENSOR_TYPE_CHOICES}
        unknown = sorted(set(handler_cls.SENSOR_TYPES) - known)
        if unknown:
            raise ImproperlyConfigured(
                f'{handler_cls.__qualname__} claims {unknown}, which are not sensor '
                f'types. Known: {", ".join(sorted(known))}.'
            )
