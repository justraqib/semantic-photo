from __future__ import annotations

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


class TextRequest(BaseModel):
    text: str


def _normalize(tensor: torch.Tensor) -> torch.Tensor:
    return tensor / tensor.norm(dim=-1, keepdim=True)


@app.on_event('startup')
def load_model() -> None:
    global model, preprocess
    model, preprocess = clip.load('ViT-B/32', device=DEVICE)
    model.eval()


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}


@app.post('/embed/text')
async def embed_text(payload: TextRequest) -> dict:
    if not payload.text:
        raise HTTPException(status_code=400, detail='text is required')

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

    try:
        image = Image.open(BytesIO(image_bytes)).convert('RGB')
    except Exception as exc:
        raise HTTPException(status_code=400, detail='invalid image') from exc

    with torch.no_grad():
        image_input = preprocess(image).unsqueeze(0).to(DEVICE)
        image_features = model.encode_image(image_input)
        normalized = _normalize(image_features)

    return {'embedding': normalized[0].cpu().tolist()}
