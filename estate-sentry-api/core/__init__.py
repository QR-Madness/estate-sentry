"""Cross-cutting pieces that belong to no single app.

A plain package, not a Django app: it holds no models and therefore no
migrations, so it needs no INSTALLED_APPS entry. Give it an AppConfig if that
ever stops being true.
"""
