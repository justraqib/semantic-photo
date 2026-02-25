from __future__ import annotations

import io
import mimetypes
import zipfile


ZIP_MIME_TYPES = {
    "application/zip",
    "application/x-zip-compressed",
    "multipart/x-zip",
}


def is_zip_upload(filename: str | None, content_type: str | None) -> bool:
    if (content_type or "").lower() in ZIP_MIME_TYPES:
        return True
    return (filename or "").lower().endswith(".zip")


def extract_image_files_from_zip(zip_bytes: bytes, max_file_size_bytes: int) -> list[tuple[str, bytes, str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            extracted: list[tuple[str, bytes, str]] = []
            for info in archive.infolist():
                if info.is_dir():
                    continue
                if info.file_size > max_file_size_bytes:
                    continue

                content_type, _ = mimetypes.guess_type(info.filename)
                if not content_type or not content_type.startswith("image/"):
                    continue

                file_bytes = archive.read(info)
                if len(file_bytes) > max_file_size_bytes:
                    continue
                extracted.append((info.filename, file_bytes, content_type))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid ZIP archive.") from exc

    return extracted
