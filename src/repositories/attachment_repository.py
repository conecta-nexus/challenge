"""Persistence operations for challenge technical attachments."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.attachment import ChallengeAttachment


class AttachmentRepository:
    """Keep attachment persistence separate from storage and HTTP concerns."""

    @staticmethod
    async def create(db: AsyncSession, attachment: ChallengeAttachment) -> ChallengeAttachment:
        db.add(attachment)
        await db.commit()
        await db.refresh(attachment)
        return attachment

    @staticmethod
    async def list_by_challenge(
        db: AsyncSession, challenge_id: UUID
    ) -> list[ChallengeAttachment]:
        query = (
            select(ChallengeAttachment)
            .where(ChallengeAttachment.challenge_id == challenge_id)
            .order_by(ChallengeAttachment.created_at.asc(), ChallengeAttachment.id.asc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_for_deletion(
        db: AsyncSession, challenge_id: UUID, attachment_id: UUID
    ) -> ChallengeAttachment | None:
        query = (
            select(ChallengeAttachment)
            .where(
                ChallengeAttachment.id == attachment_id,
                ChallengeAttachment.challenge_id == challenge_id,
            )
            .with_for_update()
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete(db: AsyncSession, attachment: ChallengeAttachment) -> None:
        await db.delete(attachment)
        await db.commit()
