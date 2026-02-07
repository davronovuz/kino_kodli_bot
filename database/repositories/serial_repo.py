from sqlalchemy import select, func, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple

from database.models import Serial, Episode


class SerialRepository:

    @staticmethod
    async def get_by_code(session: AsyncSession, code: int) -> Optional[Serial]:
        result = await session.execute(
            select(Serial)
            .options(selectinload(Serial.episodes))
            .where(Serial.code == code, Serial.is_active == True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, serial_id: int) -> Optional[Serial]:
        result = await session.execute(
            select(Serial)
            .options(selectinload(Serial.episodes))
            .where(Serial.id == serial_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def search_by_title(session: AsyncSession, query: str, limit: int = 10) -> List[Serial]:
        from sqlalchemy import or_
        result = await session.execute(
            select(Serial)
            .where(
                or_(
                    Serial.title.ilike(f"%{query}%"),
                    Serial.title_uz.ilike(f"%{query}%"),
                ),
                Serial.is_active == True,
            )
            .order_by(desc(Serial.view_count))
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def create(session: AsyncSession, **kwargs) -> Serial:
        serial = Serial(**kwargs)
        session.add(serial)
        await session.commit()
        await session.refresh(serial)
        return serial

    @staticmethod
    async def get_next_code(session: AsyncSession) -> int:
        result = await session.execute(select(func.max(Serial.code)))
        max_code = result.scalar()
        # Serial kodlari 10000 dan boshlanadi
        return max(10001, (max_code or 10000) + 1)

    @staticmethod
    async def add_episode(session: AsyncSession, **kwargs) -> Episode:
        ep = Episode(**kwargs)
        session.add(ep)
        await session.commit()
        await session.refresh(ep)
        return ep

    @staticmethod
    async def get_episode(session: AsyncSession, serial_id: int, season: int, ep_num: int) -> Optional[Episode]:
        result = await session.execute(
            select(Episode).where(
                Episode.serial_id == serial_id,
                Episode.season == season,
                Episode.episode_num == ep_num,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_episodes(session: AsyncSession, serial_id: int, season: int = None) -> List[Episode]:
        q = select(Episode).where(Episode.serial_id == serial_id, Episode.is_active == True)
        if season:
            q = q.where(Episode.season == season)
        q = q.order_by(Episode.season, Episode.episode_num)
        result = await session.execute(q)
        return result.scalars().all()

    @staticmethod
    async def get_all(session: AsyncSession, limit: int = 10, offset: int = 0) -> Tuple[List[Serial], int]:
        total = (await session.execute(
            select(func.count(Serial.id)).where(Serial.is_active == True)
        )).scalar() or 0
        result = await session.execute(
            select(Serial).where(Serial.is_active == True)
            .order_by(desc(Serial.created_at))
            .limit(limit).offset(offset)
        )
        return result.scalars().all(), total

    @staticmethod
    async def increment_view(session: AsyncSession, serial_id: int):
        await session.execute(
            update(Serial).where(Serial.id == serial_id).values(view_count=Serial.view_count + 1)
        )
        await session.commit()

    @staticmethod
    async def delete_serial(session: AsyncSession, serial_id: int) -> bool:
        result = await session.execute(delete(Serial).where(Serial.id == serial_id))
        await session.commit()
        return result.rowcount > 0