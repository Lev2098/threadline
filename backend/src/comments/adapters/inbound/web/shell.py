"""The SPA's built ``index.html`` used as the page shell for server rendering.

Vite fingerprints asset names on every build, so the shell is fetched from the
edge (``SPA_SHELL_URL``) instead of being duplicated here, and cached briefly.
The shell marks two regions that the server fills::

    <!--seo:head--> ... <!--/seo:head-->        title, meta, JSON-LD
    <div id="app"><!--seo:body--><!--/seo:body--></div>   readable content
"""

from __future__ import annotations

import logging
import re
import threading
import time
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)

TTL_SECONDS = 60
_HEAD_RE = re.compile(r"<!--seo:head-->.*?<!--/seo:head-->", re.DOTALL)
_BODY_RE = re.compile(r"<!--seo:body-->.*?<!--/seo:body-->", re.DOTALL)
_LANG_RE = re.compile(r'<html lang="[a-z-]+"')

# Used in development/tests (no edge) and if the edge is briefly unreachable on
# a cold start: still a complete, indexable document, just without the SPA.
FALLBACK_SHELL = """<!doctype html>
<html lang="uk">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <!--seo:head--><!--/seo:head-->
  </head>
  <body>
    <div id="app"><!--seo:body--><!--/seo:body--></div>
  </body>
</html>
"""

_lock = threading.Lock()
_cached: tuple[float, str] | None = None


def get_shell() -> str:
    global _cached
    url = settings.SPA_SHELL_URL
    if not url:
        return FALLBACK_SHELL
    now = time.monotonic()
    with _lock:
        if _cached and now - _cached[0] < TTL_SECONDS:
            return _cached[1]
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - URL from settings
            html = response.read().decode("utf-8")
        if "<!--seo:head-->" not in html:
            raise ValueError("SPA shell has no seo markers")
    except Exception as exc:
        log.warning("SPA shell unavailable (%s); serving %s", exc, "stale copy" if _cached else "fallback")
        return _cached[1] if _cached else FALLBACK_SHELL
    with _lock:
        _cached = (now, html)
    return html


def render_into_shell(head: str, body: str, lang: str) -> str:
    shell = get_shell()
    shell = _LANG_RE.sub(f'<html lang="{lang}"', shell, count=1)
    shell = _HEAD_RE.sub(lambda _: f"<!--seo:head-->{head}<!--/seo:head-->", shell, count=1)
    return _BODY_RE.sub(lambda _: f"<!--seo:body-->{body}<!--/seo:body-->", shell, count=1)
