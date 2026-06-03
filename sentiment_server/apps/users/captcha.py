import logging
import secrets
import string
import uuid

from django.core.cache import cache


logger = logging.getLogger(__name__)

_CAPTCHA_EXPIRY = 300  # 5 minutes
_CAPTCHA_KEY_PREFIX = "captcha:"

# Lua script: atomically GET + DELETE a key.
# Returns the stored value if it existed, nil otherwise.
# This eliminates the race window between get() and delete() that would
# allow the same captcha to be verified by two concurrent requests.
_GET_AND_DELETE_LUA = """
local value = redis.call('GET', KEYS[1])
if value then
    redis.call('DEL', KEYS[1])
end
return value
"""


def _atomic_get_and_delete(cache_key):
    """Atomically GET + DELETE a cache key via Redis Lua script.

    Falls back to the non-atomic get-then-delete pattern if the raw
    Redis client is not accessible (e.g. non-Redis cache backend).
    """
    try:
        client = cache.client.get_client()
    except Exception:
        client = None

    if client is not None:
        try:
            result = client.eval(_GET_AND_DELETE_LUA, 1, cache_key)
            if result is None:
                return None
            # redis-py returns bytes; decode to str for comparison
            if isinstance(result, bytes):
                return result.decode("utf-8")
            return result
        except Exception:
            logger.warning(
                "Redis Lua GET+DELETE failed, falling back to non-atomic path",
                exc_info=True,
            )

    # Fallback: non-atomic get + delete (still better than nothing)
    stored = cache.get(cache_key)
    if stored is not None:
        cache.delete(cache_key)
    return stored


def _generate_captcha_text(length=4):
    """Generate a random alphanumeric captcha text."""
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "")
    return "".join(secrets.choice(chars) for _ in range(length))


def _render_captcha_svg(text, width=120, height=40):
    """Render a simple SVG captcha image with noise."""
    font_size = 24
    char_width = font_size * 0.7
    total_text_width = char_width * len(text)
    x_start = (width - total_text_width) / 2
    y = (height + font_size) / 2 - 2

    # Random colors for each character
    colors = ["#2d3748", "#c53030", "#2b6cb0", "#2f855a", "#9b2c2c", "#553c9a"]

    char_svg = ""
    for i, ch in enumerate(text):
        x = x_start + i * char_width
        rotation = secrets.randbelow(30001) / 1000 - 15  # uniform(-15, 15)
        color = secrets.choice(colors)
        char_svg += (
            f'<text x="{x}" y="{y}" '
            f'font-family="Arial,Helvetica,sans-serif" '
            f'font-size="{font_size}" font-weight="bold" '
            f'fill="{color}" '
            f'transform="rotate({rotation},{x},{y - font_size * 0.35})">'
            f"{ch}</text>\n"
        )

    # Noise lines
    noise_svg = ""
    for _ in range(4):
        x1 = secrets.randbelow(10000) / 10000 * width
        y1 = secrets.randbelow(10000) / 10000 * height
        x2 = secrets.randbelow(10000) / 10000 * width
        y2 = secrets.randbelow(10000) / 10000 * height
        noise_svg += (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#cbd5e0" stroke-width="1"/>\n'
        )

    # Noise dots
    for _ in range(30):
        cx = secrets.randbelow(10000) / 10000 * width
        cy = secrets.randbelow(10000) / 10000 * height
        r = secrets.randbelow(10000) / 10000 + 1  # uniform(1, 2)
        noise_svg += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#a0aec0"/>\n'

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="#f7fafc"/>'
        f"{noise_svg}"
        f"{char_svg}"
        f"</svg>"
    )
    return svg


def generate_captcha():
    """Generate a captcha, store answer in cache, return (captcha_key, svg_content)."""
    captcha_key = uuid.uuid4().hex
    captcha_text = _generate_captcha_text()
    cache_key = f"{_CAPTCHA_KEY_PREFIX}{captcha_key}"
    cache.set(cache_key, captcha_text, _CAPTCHA_EXPIRY)
    svg = _render_captcha_svg(captcha_text)
    return captcha_key, svg


def verify_captcha(captcha_key, captcha_text):
    """Verify a captcha answer. Returns True if valid. One-time use.

    Uses an atomic Redis Lua GET+DELETE to eliminate the race window
    where two concurrent requests could both read the same captcha value.
    Falls back to non-atomic get-then-delete when the raw Redis client
    is unavailable.
    """
    if not captcha_key or not captcha_text:
        return False
    cache_key = f"{_CAPTCHA_KEY_PREFIX}{captcha_key}"
    stored = _atomic_get_and_delete(cache_key)
    if stored is None:
        return False
    return stored.upper() == captcha_text.strip().upper()
