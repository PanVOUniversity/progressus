"""Handler для рестарта бота.

Модуль обрабатывает команду рестарта бота с подтверждением:
сбрасывает все данные пользователя кроме is_premium.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.states import SurveyStates
from app.services.user_service import reset_user_data
from app.services.survey_state_service import clear_survey_state
from app.keyboards import get_restart_confirmation_keyboard, get_main_keyboard, get_gender_keyboard
from app.database import get_db

router = Router()
"""Роутер для обработки рестарта бота."""


@router.message(F.command("restart"))
@router.message(F.text.in_(["/restart", "🔄 Рестарт"]))
@router.message(F.text.startswith("/restart"))
async def cmd_restart(message: Message, state: FSMContext):
    """Обработка команды рестарта - запрос подтверждения.
    
    Показывает пользователю предупреждение о том, что будут сброшены все данные
    кроме premium статуса, и запрашивает подтверждение.
    
    Args:
        message (Message): Сообщение с текстом кнопки "🔄 Рестарт"
        state (FSMContext): Контекст FSM для перехода в состояние подтверждения
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Restart command received from user {message.from_user.id}, text: {message.text}")
    await state.set_state(SurveyStates.restart_confirmation)
    await message.answer(
        "⚠️ Внимание! Рестарт сбросит все твои данные:\n"
        "• Уровень\n"
        "• Категория и прогресс\n"
        "• Рефералы\n"
        "• Домашние задания\n"
        "• Отчеты\n\n"
        "❌ Premium статус НЕ будет сброшен.\n\n"
        "Ты уверен, что хочешь продолжить?",
        reply_markup=get_restart_confirmation_keyboard()
    )


@router.callback_query(F.data == "restart_confirm", SurveyStates.restart_confirmation)
async def restart_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение рестарта - сброс данных пользователя.
    
    Сбрасывает все данные пользователя кроме is_premium и перезапускает опросник.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки подтверждения
        state (FSMContext): Контекст FSM для сброса состояния и перехода к опроснику
    """
    user_id = callback.from_user.id
    
    # Сбрасываем данные пользователя
    async for session in get_db():
        await reset_user_data(session, user_id)
        # Очищаем сохраненное состояние опроса
        await clear_survey_state(session, user_id)
        break
    
    # Сбрасываем состояние FSM и переходим к опроснику
    await state.clear()
    await state.set_state(SurveyStates.gender)
    
    await callback.message.edit_text(
        "✅ Данные успешно сброшены!\n\n"
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
    await callback.answer("Данные сброшены!")


@router.callback_query(F.data == "restart_cancel", SurveyStates.restart_confirmation)
async def restart_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена рестарта.
    
    Отменяет операцию рестарта и возвращает пользователя в обычное состояние.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки отмены
        state (FSMContext): Контекст FSM для сброса состояния подтверждения
    """
    await state.clear()
    await callback.message.edit_text("❌ Рестарт отменен.")
    # Устанавливаем постоянную клавиатуру
    await callback.message.answer(
        "",
        reply_markup=get_main_keyboard()
    )
    await callback.answer("Рестарт отменен")
