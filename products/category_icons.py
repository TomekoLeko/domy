import re
from urllib.request import urlopen


BOOTSTRAP_ICONS_CSS_URL = "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css"

_FALLBACK_ICON_KEYS = [
    "house",
    "basket",
    "bucket-fill",
    "spray",
    "faucet",
    "badge-wc",
    "person",
    "tv",
    "fan",
    "tools",
    "wrench-adjustable",
    "tag",
]


def _fetch_bootstrap_icon_keys():
    try:
        css = urlopen(BOOTSTRAP_ICONS_CSS_URL, timeout=5).read().decode("utf-8", errors="ignore")
        keys = sorted(set(re.findall(r"\.bi-([a-z0-9-]+)::before", css)))
        if keys:
            return keys
    except Exception:
        pass
    return _FALLBACK_ICON_KEYS


_ICON_KEYS = _fetch_bootstrap_icon_keys()
ALLOWED_CATEGORY_ICONS = [(key, key) for key in _ICON_KEYS]
ALLOWED_CATEGORY_ICON_KEYS = set(_ICON_KEYS)
DEFAULT_CATEGORY_ICON = "tag" if "tag" in ALLOWED_CATEGORY_ICON_KEYS else _ICON_KEYS[0]
