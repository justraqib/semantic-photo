from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/photos", tags=["photos"])

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
JPEG_MAGIC = b"\xFF\xD8\xFF"
PNG_MAGIC = b"\x89PNG"


@router.post("/upload")
async def upload_photos(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    accepted_files = []

    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid MIME type for {file.filename}. Only image/* is allowed.",
            )

        file_bytes = await file.read()

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename} exceeds 50MB limit.",
            )

        if file.content_type in {"image/jpeg", "image/jpg"} and not file_bytes.startswith(JPEG_MAGIC):
            raise HTTPException(
                status_code=422,
                detail=f"Magic bytes do not match claimed type for {file.filename} (expected JPEG).",
            )

        if file.content_type == "image/png" and not file_bytes.startswith(PNG_MAGIC):
            raise HTTPException(
                status_code=422,
                detail=f"Magic bytes do not match claimed type for {file.filename} (expected PNG).",
            )

        accepted_files.append(
            {
                "filename": file.filename,
                "content_type": file.content_type,
                "size_bytes": len(file_bytes),
            }
        )

    return {"accepted": accepted_files, "count": len(accepted_files)}
