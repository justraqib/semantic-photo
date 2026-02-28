from __future__ import annotations

import asyncio
from io import BytesIO

import clip
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel

app = FastAPI(title='CLIP Service')

DEVICE = 'cpu'
model = None
preprocess = None
model_error: str | None = None
model_lock = asyncio.Lock()


class TextRequest(BaseModel):
    text: str


def _normalize(tensor: torch.Tensor) -> torch.Tensor:
    return tensor / tensor.norm(dim=-1, keepdim=True)


async def _load_model_once() -> bool:
    global model, preprocess, model_error
    if model is not None and preprocess is not None:
        return True
    if model_error:
        return False

    async with model_lock:
        if model is not None and preprocess is not None:
            return True
        if model_error:
            return False
        try:
            print('[clip-service] loading CLIP model ViT-B/32...', flush=True)
            loaded_model, loaded_preprocess = await asyncio.to_thread(clip.load, 'ViT-B/32', DEVICE)
            loaded_model.eval()
            model = loaded_model
            preprocess = loaded_preprocess
            model_error = None
            print('[clip-service] CLIP model ready.', flush=True)
            return True
        except Exception as exc:
            model_error = str(exc)
            print(f'[clip-service] CLIP model failed to load: {model_error}', flush=True)
            return False


@app.on_event('startup')
async def warmup_model() -> None:
    asyncio.create_task(_load_model_once())


@app.get('/health')
async def health() -> dict:
    if model is not None and preprocess is not None:
        return {'status': 'ok', 'model': 'ready'}
    if model_error:
        return {'status': 'error', 'model': 'failed', 'detail': model_error}
    return {'status': 'ok', 'model': 'loading'}


@app.post('/embed/text')
async def embed_text(payload: TextRequest) -> dict:
    if not payload.text:
        raise HTTPException(status_code=400, detail='text is required')
    if not await _load_model_once():
        raise HTTPException(status_code=503, detail=f'CLIP model unavailable: {model_error or "loading"}')

    with torch.no_grad():
        tokens = clip.tokenize([payload.text]).to(DEVICE)
        text_features = model.encode_text(tokens)
        normalized = _normalize(text_features)

    return {'embedding': normalized[0].cpu().tolist()}


@app.post('/embed/image')
async def embed_image(file: UploadFile = File(...)) -> dict:
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail='image is required')
    if not await _load_model_once():
        raise HTTPException(status_code=503, detail=f'CLIP model unavailable: {model_error or "loading"}')

    try:
        image = Image.open(BytesIO(image_bytes)).convert('RGB')
    except Exception as exc:
        raise HTTPException(status_code=400, detail='invalid image') from exc

    with torch.no_grad():
        image_input = preprocess(image).unsqueeze(0).to(DEVICE)
        image_features = model.encode_image(image_input)
        normalized = _normalize(image_features)

    return {'embedding': normalized[0].cpu().tolist()}
