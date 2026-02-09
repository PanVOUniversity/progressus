"""Сервис для сохранения и восстановления состояния опроса в БД.

Модуль предоставляет функции для сохранения прогресса опроса в БД
и восстановления состояния FSM при перезапуске бота.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import User
from typing import Optional, Dict, Any


async def save_survey_state(
    session: AsyncSession,
    user_id: int,
    state: str,
    state_data: Dict[str, Any]
) -> None:
    """Сохраняет состояние опроса в БД.
    
    Args:
        session (AsyncSession): Сессия БД
        user_id (int): ID пользователя
        state (str): Текущее состояние FSM (например, "SurveyStates:gender")
        state_data (Dict[str, Any]): Данные состояния FSM
    """
    # Сохраняем состояние и данные в JSON поле
    survey_state_data = {
        "state": state,
        "data": state_data
    }
    
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(survey_state=survey_state_data)
    )
    await session.commit()


async def restore_survey_state(
    session: AsyncSession,
    user_id: int
) -> Optional[Dict[str, Any]]:
    """Восстанавливает состояние опроса из БД.
    
    Args:
        session (AsyncSession): Сессия БД
        user_id (int): ID пользователя
        
    Returns:
        Optional[Dict[str, Any]]: Словарь с состоянием и данными, или None если состояние не найдено
    """
    result = await session.execute(
        select(User.survey_state).where(User.user_id == user_id)
    )
    survey_state = result.scalar_one_or_none()
    
    if survey_state and isinstance(survey_state, dict):
        return survey_state
    
    return None


async def clear_survey_state(
    session: AsyncSession,
    user_id: int
) -> None:
    """Очищает сохраненное состояние опроса в БД.
    
    Args:
        session (AsyncSession): Сессия БД
        user_id (int): ID пользователя
    """
    # Проверяем, существует ли пользователь
    result = await session.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Пользователь не найден, ничего не делаем
        return
    
    await session.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(survey_state=None)
    )
    await session.commit()


async def get_current_survey_state(
    session: AsyncSession,
    user_id: int
) -> Optional[str]:
    """Получает текущее состояние опроса из БД.
    
    Args:
        session (AsyncSession): Сессия БД
        user_id (int): ID пользователя
        
    Returns:
        Optional[str]: Текущее состояние (например, "SurveyStates:gender") или None
    """
    result = await session.execute(
        select(User.survey_state).where(User.user_id == user_id)
    )
    survey_state = result.scalar_one_or_none()
    
    if survey_state and isinstance(survey_state, dict):
        return survey_state.get("state")
    
    return None

