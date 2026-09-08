"""Template helpers for the dashboard."""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.template import Library
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = Library()


@register.filter
def json_for_script(value, element_id: str):
    """Embed `value` as JSON in a `<script type="application/json">` tag.

    Django's own `json_script` filter does this, but as a filter it cannot take
    the id in every version in play here, and the escaping rule is worth being
    explicit about: `<`, `>` and `&` are escaped so a zone named with a stray
    `</script>` cannot break out of the tag and become markup. Zone names are
    user-supplied.
    """
    payload = json.dumps(value, cls=DjangoJSONEncoder)
    payload = (
        payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )
    return format_html(
        '<script id="{}" type="application/json">{}</script>',
        element_id,
        mark_safe(payload),  # noqa: S308 — escaped above; format_html would double-encode
    )
