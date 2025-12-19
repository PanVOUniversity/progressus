"""Handler для обработки согласия на персональные данные.

Модуль обрабатывает нажатие кнопки согласия на обработку ПД,
сохраняет согласие в БД и переводит пользователя к опроснику.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.models import User
from app.states import SurveyStates
from app.keyboards import get_gender_keyboard, get_main_keyboard
from app.database import get_db
from app.services.survey_state_service import save_survey_state
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = Router()
"""Роутер для обработки согласия на обработку ПД."""


@router.callback_query(F.data == "privacy_consent_accepted")
async def privacy_consent_accepted(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки согласия на обработку персональных данных.
    
    Сохраняет согласие пользователя в БД с текущей датой и временем,
    затем переводит пользователя к первому вопросу опросника.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки
        state (FSMContext): Контекст конечного автомата для перехода к опроснику
    """
    user_id = callback.from_user.id
    
    # Сохраняем согласие в БД
    async for session in get_db():
        await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(
                privacy_consent_accepted=True,
                privacy_consent_date=datetime.utcnow()
            )
        )
        await session.commit()
        break
    
    # Переходим к опроснику
    await state.set_state(SurveyStates.gender)
    
    # Сохраняем начальное состояние опроса в БД
    async for session in get_db():
        try:
            state_data = await state.get_data()
            await save_survey_state(
                session,
                callback.from_user.id,
                str(SurveyStates.gender),
                state_data
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
        break
    
    await callback.message.edit_text(
        "👋 Привет! Ты попал в пространство развития Progressus.\n\n"
        "📈 Progressus - твой лучший персональный наставник.\n\n"
        "✨ Топовые ролевые модели\n"
        "📝 Персональные задания\n\n"
        "Именно здесь ты реализуешь весь свой потенциал, но для начала "
        "давай пройдем небольшой опрос, чтобы лучше тебя понять.\n\n"
        "Твой пол?",
        reply_markup=get_gender_keyboard()
    )
    # Устанавливаем постоянную клавиатуру
    await callback.message.answer(
        "",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

