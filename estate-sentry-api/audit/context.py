"""The hook a view uses to tell the audit middleware what it just did.

The middleware sees an HttpRequest and a status code, which is enough for most
entries. It is not enough for the two that matter most: on a login the request
is still anonymous when the view runs, so `request.user` names nobody, and on a
*failed* login there is no user to name at all — only an attempted username,
which the middleware cannot read because the body has already been consumed by
the parser.

So views enrich. Anything set here is merged over what the middleware inferred.
"""

ATTRIBUTE = '_audit_context'


def _underlying(request):
    """The Django HttpRequest behind a DRF Request, if there is one.

    This matters: DRF's `Request` proxies attribute *reads* to the request it
    wraps, but a `setattr` lands on the wrapper — and the middleware only ever
    sees the wrapped HttpRequest. Stashing context on the DRF request would
    silently go nowhere.
    """
    return getattr(request, '_request', request)


def set_audit_context(request, **fields):
    """Record fields for the audit entry this request will produce.

    Recognised: `actor`, `actor_username`, `target_type`, `target_id`,
    `outcome`, and `metadata` (a dict, merged rather than replaced).
    """
    target = _underlying(request)

    context = getattr(target, ATTRIBUTE, None)
    if context is None:
        context = {}
        setattr(target, ATTRIBUTE, context)

    metadata = fields.pop('metadata', None)
    if metadata:
        context.setdefault('metadata', {}).update(metadata)

    context.update(fields)
    return context


def get_audit_context(request):
    return getattr(_underlying(request), ATTRIBUTE, None) or {}
