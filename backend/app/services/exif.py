from __future__ import annotations

from io import BytesIO

import exifread


def _to_float(value) -> float:
    if hasattr(value, "num") and hasattr(value, "den"):
        return float(value.num) / float(value.den)
    return float(value)


def _dms_to_decimal(dms_values, ref: str | None) -> float | None:
    if not dms_values or len(dms_values) < 3:
        return None

    degrees = _to_float(dms_values[0])
    minutes = _to_float(dms_values[1])
    seconds = _to_float(dms_values[2])
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)

    if ref in {"S", "W"}:
        decimal *= -1
    return decimal


def _get_tag_value(tags: dict, key: str):
    tag = tags.get(key)
    if tag is None:
        return None
    value = getattr(tag, "values", tag)
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value


def extract_exif(image_bytes: bytes) -> dict:
    tags = exifread.process_file(BytesIO(image_bytes), details=False)

    taken_at_tag = tags.get("EXIF DateTimeOriginal")
    lat_tag = tags.get("GPS GPSLatitude")
    lat_ref_tag = tags.get("GPS GPSLatitudeRef")
    lng_tag = tags.get("GPS GPSLongitude")
    lng_ref_tag = tags.get("GPS GPSLongitudeRef")
    camera_make_tag = tags.get("Image Make")
    camera_model_tag = tags.get("Image Model")

    width = _get_tag_value(tags, "EXIF ExifImageWidth")
    if width is None:
        width = _get_tag_value(tags, "Image ImageWidth")

    height = _get_tag_value(tags, "EXIF ExifImageLength")
    if height is None:
        height = _get_tag_value(tags, "Image ImageLength")

    gps_lat = _dms_to_decimal(
        getattr(lat_tag, "values", None),
        str(getattr(lat_ref_tag, "values", [None])[0]) if lat_ref_tag else None,
    )
    gps_lng = _dms_to_decimal(
        getattr(lng_tag, "values", None),
        str(getattr(lng_ref_tag, "values", [None])[0]) if lng_ref_tag else None,
    )

    return {
        "taken_at": str(taken_at_tag) if taken_at_tag else None,
        "gps_lat": gps_lat,
        "gps_lng": gps_lng,
        "camera_make": str(camera_make_tag) if camera_make_tag else None,
        "camera_model": str(camera_model_tag) if camera_model_tag else None,
        "width": int(_to_float(width)) if width is not None else None,
        "height": int(_to_float(height)) if height is not None else None,
    }
