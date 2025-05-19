from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import List, Optional

engine = create_async_engine('sqlite+aiosqlite:///cinema_bot.db')


class Base(DeclarativeBase):
    pass


class SearchHistory(Base):
    __tablename__ = 'search_history'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    query: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow() + timedelta(hours=3)
    )
    movie_title: Mapped[str]
    movie_id: Mapped[str]


class MovieStats(Base):
    __tablename__ = 'movie_stats'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    movie_id: Mapped[str]
    movie_title: Mapped[str]
    times_shown: Mapped[int] = mapped_column(default=1)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def add_search_history(user_id: int, query: str, movie_title: str, movie_id: str):
    async with AsyncSession(engine) as session:
        history = SearchHistory(
            user_id=user_id,
            query=query,
            movie_title=movie_title,
            movie_id=movie_id
        )
        session.add(history)
        await session.commit()


async def get_search_history(user_id: int) -> List[SearchHistory]:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(SearchHistory)
            .where(SearchHistory.user_id == user_id)
            .order_by(SearchHistory.timestamp.desc())
            .limit(10)
        )
        return result.scalars().all()


async def update_movie_stats(user_id: int, movie_id: str, movie_title: str):
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(MovieStats)
            .where(MovieStats.user_id == user_id)
            .where(MovieStats.movie_id == movie_id)
        )
        stats = result.scalar_one_or_none()

        if stats:
            stats.times_shown += 1
        else:
            stats = MovieStats(
                user_id=user_id,
                movie_id=movie_id,
                movie_title=movie_title
            )
            session.add(stats)

        await session.commit()


async def get_user_stats(user_id: int) -> List[MovieStats]:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(MovieStats)
            .where(MovieStats.user_id == user_id)
            .order_by(MovieStats.times_shown.desc())
            .limit(10)
        )
        return result.scalars().all()
