"""Сервис для работы с пользователями.

Модуль содержит функции для работы с пользователями в БД:
создание, получение и обновление данных пользователей.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.models import User, Survey, Report
from typing import Optional
from datetime import datetime, timedelta


async def get_or_create_user(session: AsyncSession, user_id: int, username: Optional[str] = None) -> User:
    """Получает пользователя из БД или создает нового.
    
    Ищет пользователя по user_id. Если пользователь не найден,
    создает новую запись с указанными параметрами.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        username (Optional[str]): Username пользователя в Telegram
        
    Returns:
        User: Объект пользователя из БД
        
    Note:
        Автоматически коммитит транзакцию при создании нового пользователя.
    """
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            user_id=user_id,
            username=username,
            level=0,
            is_premium=False,
            privacy_consent_accepted=False,
            category_progress={}
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user


async def update_user_level(session: AsyncSession, user_id: int, new_level: int) -> User:
    """Обновляет уровень пользователя.
    
    Обновляет уровень пользователя с ограничением максимумом 10.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        new_level (int): Новый уровень пользователя (будет ограничен до 10)
        
    Returns:
        User: Обновленный объект пользователя
        
    Note:
        Уровень автоматически ограничивается максимумом 10.
    """
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(level=min(new_level, 10))  # Максимум 10
    )
    await session.commit()
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one()


async def update_user_category(session: AsyncSession, user_id: int, category: str) -> User:
    """Обновляет категорию пользователя."""
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(category=category)
    )
    await session.commit()
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one()


async def update_user_homework(session: AsyncSession, user_id: int, homework: str) -> Optional[User]:
    """Обновляет текущее домашнее задание пользователя.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        homework (str): Текст нового домашнего задания
        
    Returns:
        Optional[User]: Обновленный объект пользователя или None, если пользователь не найден
    """
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(current_homework=homework)
    )
    await session.commit()
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()


async def update_user_personality(session: AsyncSession, user_id: int, personality: str) -> User:
    """Обновляет выбранную личность коуча пользователя.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        personality (str): Ключ личности (andrew_tate/greg_plitt/markaryan)
        
    Returns:
        User: Обновленный объект пользователя
    """
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(personality=personality)
    )
    await session.commit()
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one()


async def is_premium_active(session: AsyncSession, user_id: int) -> bool:
    """Проверяет, активен ли premium доступ у пользователя.
    
    Проверяет флаг is_premium и дату окончания premium_expires_at.
    Если premium_expires_at истек, автоматически сбрасывает is_premium.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        
    Returns:
        bool: True если premium активен, False иначе
    """
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_premium:
        return False
    
    # Проверяем дату окончания
    if user.premium_expires_at:
        now = datetime.utcnow()
        if user.premium_expires_at.replace(tzinfo=None) < now:
            # Премиум истек, сбрасываем
            await session.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(is_premium=False, premium_expires_at=None)
            )
            await session.commit()
            return False
    
    return True


async def activate_premium(session: AsyncSession, user_id: int, months: int = 1) -> User:
    """Активирует premium доступ на указанное количество месяцев.
    
    Если у пользователя уже есть активный премиум, добавляет месяцы к текущей дате окончания.
    Иначе устанавливает дату окончания на указанное количество месяцев вперед.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        months (int): Количество месяцев премиума (по умолчанию 1)
        
    Returns:
        User: Обновленный объект пользователя
    """
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    now = datetime.utcnow()
    
    # Если премиум уже активен и не истек, добавляем месяцы к текущей дате
    if user.is_premium and user.premium_expires_at:
        expires_at = user.premium_expires_at.replace(tzinfo=None)
        if expires_at > now:
            # Добавляем месяцы к существующей дате
            new_expires_at = expires_at + timedelta(days=30 * months)
        else:
            # Премиум истек, начинаем с текущей даты
            new_expires_at = now + timedelta(days=30 * months)
    else:
        # Устанавливаем новую дату окончания
        new_expires_at = now + timedelta(days=30 * months)
    
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(
            is_premium=True,
            premium_expires_at=new_expires_at
        )
    )
    await session.commit()
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one()


async def deactivate_premium(session: AsyncSession, user_id: int) -> User:
    """Деактивирует premium доступ пользователя (мгновенный снос подписки).
    
    Сбрасывает флаг is_premium и дату окончания premium_expires_at.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        
    Returns:
        User: Обновленный объект пользователя
    """
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(
            is_premium=False,
            premium_expires_at=None
        )
    )
    await session.commit()
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one()


async def reset_user_data(session: AsyncSession, user_id: int) -> User:
    """Сбрасывает данные пользователя, кроме is_premium.
    
    Сбрасывает уровень, категорию, прогресс, рефералов, домашние задания,
    персонализацию, консультации, удаляет все опросы и отчеты, но сохраняет статус premium доступа.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        
    Returns:
        User: Обновленный объект пользователя
        
    Note:
        is_premium не сбрасывается, все остальные данные сбрасываются.
        Surveys и Reports удаляются полностью.
    """
    # Удаляем все опросы пользователя
    await session.execute(
        delete(Survey).where(Survey.user_id == user_id)
    )
    
    # Удаляем все отчеты пользователя
    await session.execute(
        delete(Report).where(Report.user_id == user_id)
    )
    
    # Сбрасываем данные пользователя
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(
            level=0,
            category=None,
            category_progress={},
            personality=None,
            name=None,
            gender=None,
            age=None,
            values=None,
            development_spheres=None,
            goal_3months=None,
            roadmap=None,
            referrals=[],
            referrer_id=None,
            last_report=None,
            current_homework=None,
            homework_needs_revision=False,
            personalization_data=None,
            consultation_used=False,
            survey_state=None
        )
    )
    await session.commit()
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one()

