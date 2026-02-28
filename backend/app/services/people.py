from __future__ import annotations

from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.photo import Photo
from app.models.tag import PhotoTag, Tag

PERSON_NAME_PREFIX = "person:"
PERSON_CLUSTER_PREFIX = "person_cluster:"


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return sum(x * x for x in a) ** 0.5


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    denom = _norm(a) * _norm(b)
    if denom == 0:
        return 0.0
    return _dot(a, b) / denom


def _to_float_list(vector) -> list[float]:
    if vector is None:
        return []
    if isinstance(vector, list):
        return [float(x) for x in vector]
    try:
        return [float(x) for x in list(vector)]
    except TypeError:
        return []


async def _ensure_tag(db: AsyncSession, tag_name: str) -> Tag:
    tag = (await db.execute(select(Tag).where(Tag.name == tag_name))).scalar_one_or_none()
    if tag is None:
        tag = Tag(name=tag_name)
        db.add(tag)
        await db.flush()
    return tag


async def _clear_person_tags(db: AsyncSession, photo_id) -> None:
    await db.execute(
        PhotoTag.__table__.delete().where(
            PhotoTag.photo_id == photo_id,
            PhotoTag.tag_id.in_(
                select(Tag.id).where(
                    or_(
                        Tag.name.like(f"{PERSON_NAME_PREFIX}%"),
                        Tag.name.like(f"{PERSON_CLUSTER_PREFIX}%"),
                    )
                )
            ),
        )
    )


async def auto_assign_person_cluster(
    db: AsyncSession,
    photo: Photo,
    similarity_threshold: float = 0.86,
) -> str | None:
    source_embedding = _to_float_list(photo.embedding)
    if not source_embedding:
        return None

    rows = (
        await db.execute(
            select(Photo.embedding, Tag.name)
            .join(PhotoTag, PhotoTag.photo_id == Photo.id)
            .join(Tag, Tag.id == PhotoTag.tag_id)
            .where(
                Photo.user_id == photo.user_id,
                Photo.is_deleted.is_(False),
                Photo.embedding.is_not(None),
                Photo.id != photo.id,
                or_(
                    Tag.name.like(f"{PERSON_NAME_PREFIX}%"),
                    Tag.name.like(f"{PERSON_CLUSTER_PREFIX}%"),
                ),
            )
            .order_by(Photo.uploaded_at.desc())
            .limit(600)
        )
    ).all()

    best_tag_name: str | None = None
    best_score = 0.0
    for candidate_embedding, candidate_tag_name in rows:
        candidate_vector = _to_float_list(candidate_embedding)
        if not candidate_vector:
            continue
        score = _cosine_similarity(source_embedding, candidate_vector)
        if score > best_score:
            best_score = score
            best_tag_name = candidate_tag_name

    if best_tag_name is None or best_score < similarity_threshold:
        best_tag_name = f"{PERSON_CLUSTER_PREFIX}{uuid4().hex[:10]}"

    tag = await _ensure_tag(db, best_tag_name)
    await _clear_person_tags(db, photo.id)
    db.add(PhotoTag(photo_id=photo.id, tag_id=tag.id, confidence=best_score or 1.0, source="auto_people"))
    return best_tag_name
