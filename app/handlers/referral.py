"""Handler для команды /ref - получение реферальной ссылки.

Модуль обрабатывает команду /ref и показывает пользователю его
реферальную ссылку и статистику по рефералам.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User
from app.services.referral_service import generate_referral_link, get_referral_stats
from app.database import get_db
from app.keyboards import get_share_referral_keyboard, get_main_keyboard

router = Router()
"""Роутер для обработки реферальной системы."""


async def send_referral_info(message: Message, bot: Bot, state: FSMContext = None):
    """Отправляет информацию о реферальной ссылке пользователю.
    
    Args:
        message (Message): Сообщение от пользователя
        bot (Bot): Экземпляр бота для получения username бота
        state (FSMContext, optional): Контекст FSM для сохранения message_id
    """
    user_id = message.from_user.id
    
    # Получаем username бота если не указан в config
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    
    # Генерируем ссылку
    referral_link = generate_referral_link(user_id, bot_username)
    
    # Получаем статистику
    async for session in get_db():
        stats = await get_referral_stats(session, user_id)
        break
    
    # Формируем сообщение
    stats_text = (
        f"📊 Статистика рефералов:\n"
        f"• Всего рефералов: {stats['total_referrals']}\n"
        f"• Оплатили премиум: {stats['paid_referrals']}\n"
    )
    
    if stats['referrals_to_premium'] > 0:
        stats_text += (
            f"• До месяца бесплатного премиума: "
            f"{stats['referrals_to_premium']} реферал(ов) "
            f"({stats['referrals_for_premium']} = +1 месяц премиума)"
        )
    else:
        stats_text += "• ✅ Достаточно рефералов для получения месяца бесплатного премиума!"
    
    sent_message = await message.answer(
        f"🔗 Твоя реферальная ссылка:\n{referral_link}\n\n{stats_text}",
        reply_markup=get_share_referral_keyboard(referral_link)
    )
    
    # Сохраняем message_id для возможности удаления
    if state:
        await state.update_data(last_referral_message_id=sent_message.message_id)


@router.message(F.command("ref"))
@router.message(F.command("referral"))
@router.message(F.text.in_(["/ref", "/referral", "🔗 Реферальная ссылка"]))
@router.message(F.text.startswith("/ref"))
@router.message(F.text.startswith("/referral"))
async def cmd_referral(message: Message, state: FSMContext):
    """Обработка команды /ref или кнопки реферальной ссылки - показ реферальной ссылки и статистики.
    
    Генерирует реферальную ссылку пользователя, получает статистику
    по рефералам и отправляет пользователю сообщение с ссылкой,
    статистикой и кнопкой для поделиться ссылкой.
    
    Args:
        message (Message): Сообщение с командой /ref, /referral или текстом кнопки
        state (FSMContext): Контекст FSM для сохранения message_id
    """
    await send_referral_info(message, message.bot, state)


@router.message(F.command("continue"))
@router.message(F.command("chat"))
@router.message(F.text.in_(["/continue", "/chat", "Продолжить переписку"]))
@router.message(F.text.startswith("/continue"))
@router.message(F.text.startswith("/chat"))
async def cmd_continue(message: Message, state: FSMContext):
    """Обработка команды продолжить переписку - удаляет последнее сообщение с реферальной ссылкой.
    
    Удаляет последнее сообщение бота с реферальной ссылкой, если оно было отправлено
    после команды /ref. Позволяет пользователю продолжить обычную переписку с ботом.
    
    Args:
        message (Message): Сообщение с командой /continue, /chat или "Продолжить переписку"
        state (FSMContext): Контекст FSM для получения сохраненного message_id
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Continue command received from user {message.from_user.id}, text: {message.text}")
    user_id = message.from_user.id
    
    # Получаем сохраненный message_id последнего сообщения с реферальной ссылкой
    data = await state.get_data()
    last_referral_message_id = data.get("last_referral_message_id")
    
    if last_referral_message_id:
        try:
            # Удаляем сообщение с реферальной ссылкой
            await message.bot.delete_message(chat_id=user_id, message_id=last_referral_message_id)
            # Очищаем сохраненный message_id
            await state.update_data(last_referral_message_id=None)
            await message.answer("✅ Готово! Можешь продолжать переписку.")
        except Exception as e:
            # Если сообщение уже удалено или произошла ошибка, просто продолжаем
            await message.answer("✅ Готово! Можешь продолжать переписку.")
    else:
        await message.answer("Нет сообщений с реферальной ссылкой для удаления.")
