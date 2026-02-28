from __future__ import annotations

_HEIF_REGISTERED = False


def register_optional_image_codecs() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        # HEIC/HEIF support stays optional. JPEG/PNG/WebP continue to work.
        pass
    _HEIF_REGISTERED = True
