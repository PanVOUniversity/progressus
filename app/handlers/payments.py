"""Handlers для обработки платежей (Telegram Payments с заглушкой).

Модуль обрабатывает оплату premium доступа. В текущей версии используется
заглушка - premium активируется автоматически без реального платежа.
Реальный код обработки платежей закомментирован и может быть активирован
после настройки PROVIDER_TOKEN в BotFather.
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, PreCheckoutQuery, SuccessfulPayment, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models import Payment, User
from app.services.user_service import activate_premium
from app.services.referral_service import add_referral_on_payment
from app.database import get_db
from datetime import datetime

router = Router()
"""Роутер для обработки платежей."""


@router.callback_query(F.data == "payment_start")
async def start_payment(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Обработка начала процесса оплаты (заглушка).
    
    В текущей версии сразу активирует premium доступ без реального платежа:
    создает запись о платеже со статусом "completed", активирует premium,
    повышает уровень пользователя до 1 и обрабатывает реферальную систему.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки оплаты
        bot (Bot): Экземпляр бота для отправки сообщений
        
    Note:
        Это заглушка для тестирования. Для реальных платежей нужно раскомментировать
        код обработки pre_checkout_query и successful_payment.
    """
    # ЗАГЛУШКА: вместо реальной оплаты сразу активируем premium
    user_id = callback.from_user.id
    
    async for session in get_db():
        # Создаем запись о платеже (заглушка)
        payment = Payment(
            user_id=user_id,
            payment_id=f"stub_{user_id}_{int(datetime.utcnow().timestamp())}",
            amount=settings.PREMIUM_PRICE,
            status="completed"
        )
        session.add(payment)
        
        # Активируем premium на 1 месяц
        await activate_premium(session, user_id, months=1)
        
        # Повышаем уровень до 1 при первой оплате
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one()
        if user.level == 0:
            from sqlalchemy import update
            await session.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(level=1)
            )
        
        # Обрабатываем рефералку
        referrer_id = await add_referral_on_payment(session, user_id)
        if referrer_id:
            # Даем месяц бесплатного премиума рефереру
            await activate_premium(session, referrer_id, months=1)
        
        await session.commit()
        break
    
    # Проверяем, нужно ли продолжить генерацию роадмапа
    data = await state.get_data()
    pending_roadmap = data.get("pending_roadmap", False)
    
    if pending_roadmap:
        # Убираем флаг и продолжаем генерацию роадмапа
        await state.update_data(pending_roadmap=False)
        await callback.message.edit_text("✅ Premium доступ активирован!")
        await callback.answer("Premium активирован, генерирую роадмап...")
        
        # Импортируем функцию генерации роадмапа
        from app.handlers.survey import generate_roadmap_after_payment
        await generate_roadmap_after_payment(callback.message, state, bot)
    else:
        await callback.message.edit_text(
            "✅ Premium доступ активирован!\n\n"
            "Теперь ты получаешь ежедневные задания и можешь отправлять отчеты через /report"
        )
        await callback.answer()


# ЗАГЛУШКА: Закомментирован реальный код обработки платежей
# Раскомментируй когда будешь готов к реальным платежам

# @router.pre_checkout_query()
# async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
#     """Валидация платежа перед подтверждением."""
#     # ЗАГЛУШКА: автоматически одобряем все платежи
#     await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
# 
# 
# @router.message(F.successful_payment)
# async def successful_payment_handler(message: Message, bot: Bot):
#     """Обработка успешного платежа."""
#     user_id = message.from_user.id
#     payment = message.successful_payment
#     
#     async for session in get_db():
#         # Сохраняем платеж
#         db_payment = Payment(
#             user_id=user_id,
#             payment_id=payment.telegram_payment_charge_id,
#             amount=payment.total_amount,
#             status="completed"
#         )
#         session.add(db_payment)
#         
#         # Активируем premium и повышаем уровень до 1
#         await session.execute(
#             User.__table__.update()
#             .where(User.user_id == user_id)
#             .values(is_premium=True, level=1)
#         )
#         
#         # Обрабатываем рефералку
#         referrer_id = await add_referral_on_payment(session, user_id)
#         if referrer_id:
#             await update_user_level(session, referrer_id, 2)
#         
#         await session.commit()
#         break
#     
#     await message.answer(
#         "✅ Premium доступ активирован!\n\n"
#         "Теперь ты получаешь ежедневные задания и можешь отправлять отчеты через /report"
#     )

