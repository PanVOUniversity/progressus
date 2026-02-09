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
from app.keyboards import get_gender_keyboard, get_main_keyboard, get_payment_keyboard
from app.database import get_db
from app.services.survey_state_service import save_survey_state
from app.services.user_service import is_premium_active
from app.config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = Router()
"""Роутер для обработки согласия на обработку ПД."""


@router.callback_query(F.data == "privacy_consent_accepted")
async def privacy_consent_accepted(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки согласия на обработку персональных данных.
    
    Сохраняет согласие пользователя в БД с текущей датой и временем,
    затем проверяет premium доступ. Если premium нет - показывает экран оплаты,
    если есть - переводит к первому вопросу опросника.
    
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
        
        # Проверяем premium доступ
        premium_active = await is_premium_active(session, user_id)
        
        if not premium_active:
            # Premium нет - показываем экран оплаты
            price_rub = settings.PREMIUM_PRICE // 100
            await callback.message.edit_text(
                "Согласие принято!\n\n"
                "Для начала работы нужен Premium доступ\n\n"
                "Premium включает:\n"
                "- Персональный роадмап достижения цели\n"
                "- Ежедневные задания от ИИ-коуча\n"
                "- Обратная связь по отчетам\n"
                "- Трекинг прогресса\n\n"
                f"Стоимость: {price_rub} руб./месяц\n\n"
                "Оплати подписку, чтобы начать свой путь к успеху!",
                reply_markup=get_payment_keyboard()
            )
            await callback.answer()
            break
        
        # Premium есть - переходим к опроснику
        await state.set_state(SurveyStates.gender)
        
        # Сохраняем начальное состояние опроса в БД
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
        
        await callback.message.edit_text(
            "Привет! Ты попал в пространство развития Progressus.\n\n"
            "Progressus - твой лучший персональный наставник.\n\n"
            "- Топовые ролевые модели\n"
            "- Персональные задания\n\n"
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
        break

