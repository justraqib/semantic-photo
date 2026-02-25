from __future__ import annotations

import io
import mimetypes
import zipfile

ZIP_MIME_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "multipart/x-zip",
}

JPEG_MAGIC = b"\xFF\xD8\xFF"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_RIFF = b"RIFF"
WEBP_TYPE = b"WEBP"
GIF87A = b"GIF87a"
GIF89A = b"GIF89a"


def is_zip_upload(filename: str | None, content_type: str | None) -> bool:
    normalized_type = (content_type or "").lower()
    if normalized_type in ZIP_MIME_TYPES:
        return True
    return (filename or "").lower().endswith(".zip")


def detect_image_content_type(filename: str | None, file_bytes: bytes) -> str | None:
    guessed, _ = mimetypes.guess_type(filename or "")
    if guessed and guessed.startswith("image/"):
        return guessed

    if file_bytes.startswith(JPEG_MAGIC):
        return "image/jpeg"
    if file_bytes.startswith(PNG_MAGIC):
        return "image/png"
    if file_bytes.startswith(GIF87A) or file_bytes.startswith(GIF89A):
        return "image/gif"
    if len(file_bytes) >= 12 and file_bytes[:4] == WEBP_RIFF and file_bytes[8:12] == WEBP_TYPE:
        return "image/webp"
    # HEIF/HEIC files usually contain `ftypheic`/`ftypheif` around byte offset 4.
    if len(file_bytes) >= 12 and file_bytes[4:8] == b"ftyp" and file_bytes[8:12] in {
        b"heic",
        b"heif",
        b"heix",
        b"hevc",
    }:
        return "image/heic"
    return None


def extract_image_files_from_zip(zip_bytes: bytes, max_file_size_bytes: int) -> list[tuple[str, bytes, str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            extracted: list[tuple[str, bytes, str]] = []
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if info.file_size > max_file_size_bytes:
                    continue

                file_bytes = archive.read(info)
                if len(file_bytes) > max_file_size_bytes:
                    continue
                content_type = detect_image_content_type(info.filename, file_bytes)
                if not content_type:
                    continue

                extracted.append((info.filename, file_bytes, content_type))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid ZIP archive.") from exc

    return extracted
