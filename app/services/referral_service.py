"""Сервис для работы с реферальной системой.

Модуль содержит функции для работы с реферальной системой:
генерация реферальных ссылок, обработка рефералов при регистрации
и оплате, получение статистики по рефералам.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.models import User
from typing import Optional
from app.config import settings


def generate_referral_link(user_id: int, bot_username: Optional[str] = None) -> str:
    """Генерирует реферальную ссылку для пользователя.
    
    Создает ссылку формата: https://t.me/{bot_username}?start=ref{user_id}
    
    Args:
        user_id (int): Telegram ID пользователя
        bot_username (Optional[str]): Username бота без @. Если None, используется из config
        
    Returns:
        str: Реферальная ссылка для пользователя
        
    Example:
        .. code-block:: python
        
            link = generate_referral_link(123456, "my_bot")
            # Результат: "https://t.me/my_bot?start=ref123456"
    """
    username = bot_username or settings.BOT_USERNAME
    if not username:
        # Если username не указан, используем формат без username
        return f"https://t.me/your_bot?start=ref{user_id}"
    return f"https://t.me/{username}?start=ref{user_id}"


async def process_referral(session: AsyncSession, user_id: int, referrer_id: int) -> None:
    """Обрабатывает реферала при регистрации: сохраняет referrer_id для пользователя.
    
    Устанавливает связь между новым пользователем и его реферером
    при регистрации через реферальную ссылку.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID нового пользователя
        referrer_id (int): Telegram ID реферера
    """
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(referrer_id=referrer_id)
    )
    await session.commit()


async def add_referral_on_payment(session: AsyncSession, user_id: int) -> Optional[int]:
    """Добавляет реферала в список реферера при оплате premium доступа.
    
    Когда пользователь оплачивает premium доступ, его добавляют в список
    рефералов его реферера. Если у реферера набирается нужное количество
    оплативших рефералов (из настроек), возвращается его ID для получения
    месяца бесплатного премиума.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя, который оплатил premium
        
    Returns:
        Optional[int]: ID реферера, если нужно дать ему месяц премиума,
            иначе None
        
    Note:
        Месяц премиума дается только если у реферера набралось нужное количество
        оплативших рефералов (настраивается через REFERRALS_FOR_PREMIUM).
    """
    from app.services.user_service import is_premium_active
    
    # Получаем пользователя
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.referrer_id:
        return None
    
    referrer_id = user.referrer_id
    
    # Получаем реферера
    result = await session.execute(select(User).where(User.user_id == referrer_id))
    referrer = result.scalar_one_or_none()
    
    if not referrer:
        return None
    
    # Добавляем реферала в список (только если его там еще нет)
    referrals = referrer.referrals or []
    if user_id not in referrals:
        referrals.append(user_id)
        
        await session.execute(
            update(User)
            .where(User.user_id == referrer_id)
            .values(referrals=referrals)
        )
        await session.commit()
    
    # Подсчитываем количество оплативших рефералов (проверяем активность премиума)
    # Важно: проверяем только тех, кто реально оплатил и имеет активный премиум
    paid_referrals_count = 0
    for ref_id in referrals:
        # Проверяем, что реферал имеет активный премиум (оплатил и не истек)
        if await is_premium_active(session, ref_id):
            paid_referrals_count += 1
    
    # Проверяем, нужно ли дать месяц премиума рефереру
    # Премиум дается только если достаточно рефералов РЕАЛЬНО оплатили (имеют активный премиум)
    if paid_referrals_count >= settings.REFERRALS_FOR_PREMIUM:
        return referrer_id
    
    return None


async def get_referral_stats(session: AsyncSession, user_id: int) -> dict:
    """Получает статистику рефералов пользователя.
    
    Собирает информацию о количестве рефералов пользователя,
    количестве оплативших рефералов и сколько осталось до получения
    месяца бесплатного премиума.
    
    Args:
        session (AsyncSession): Асинхронная сессия БД
        user_id (int): Telegram ID пользователя
        
    Returns:
        dict: Словарь со статистикой:
            - total_referrals (int): Общее количество рефералов
            - paid_referrals (int): Количество оплативших рефералов
            - referrals_to_premium (int): Сколько рефералов осталось до получения месяца премиума
            - referrals_for_premium (int): Необходимое количество рефералов для получения премиума
            
    Note:
        Проверяет активность премиума у каждого реферала через is_premium_active.
    """
    from app.services.user_service import is_premium_active
    
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        return {
            "total_referrals": 0,
            "paid_referrals": 0,
            "referrals_to_premium": settings.REFERRALS_FOR_PREMIUM,
            "referrals_for_premium": settings.REFERRALS_FOR_PREMIUM
        }
    
    referrals = user.referrals or []
    total_referrals = len(referrals)
    
    # Подсчитываем оплативших (проверяем активность премиума)
    paid_referrals = 0
    for ref_id in referrals:
        if await is_premium_active(session, ref_id):
            paid_referrals += 1
    
    # Сколько осталось до получения месяца премиума
    referrals_to_premium = max(0, settings.REFERRALS_FOR_PREMIUM - paid_referrals)
    
    return {
        "total_referrals": total_referrals,
        "paid_referrals": paid_referrals,
        "referrals_to_premium": referrals_to_premium,
        "referrals_for_premium": settings.REFERRALS_FOR_PREMIUM
    }

