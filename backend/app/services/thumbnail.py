from __future__ import annotations

from io import BytesIO

from PIL import Image


def generate_thumbnail(image_bytes: bytes) -> bytes:
    input_buffer = BytesIO(image_bytes)
    output_buffer = BytesIO()

    with Image.open(input_buffer) as image:
        image.thumbnail((400, 400))
        image.convert("RGB").save(output_buffer, format="WEBP")

    return output_buffer.getvalue()
