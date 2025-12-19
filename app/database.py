"""Подключение к PostgreSQL через asyncpg.

Модуль настраивает асинхронное подключение к базе данных PostgreSQL
с использованием SQLAlchemy и asyncpg драйвера.

Attributes:
    engine: Асинхронный движок SQLAlchemy для подключения к БД
    async_session_maker: Фабрика для создания сессий БД
    Base: Базовый класс для всех моделей SQLAlchemy
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# Создаем async engine
engine = create_async_engine(
    settings.DB_URL,
    echo=settings.ENVIRONMENT == "development",
    future=True
)
"""Асинхронный движок SQLAlchemy для подключения к PostgreSQL."""

# Создаем async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)
"""Фабрика для создания асинхронных сессий БД."""

# Базовый класс для моделей
Base = declarative_base()
"""Базовый класс для всех моделей SQLAlchemy."""


async def get_db() -> AsyncSession:
    """Dependency для получения сессии БД.
    
    Используется как dependency injection для FastAPI и обработчиков.
    Автоматически закрывает сессию после использования.
    
    Yields:
        AsyncSession: Асинхронная сессия базы данных
        
    Example:
        .. code-block:: python
        
            async for session in get_db():
                user = await session.get(User, user_id)
                break
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

