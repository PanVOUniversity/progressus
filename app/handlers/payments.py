"""Handlers для обработки платежей через Telegram Payments.

Модуль обрабатывает оплату premium доступа через Telegram Payments API.
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, PreCheckoutQuery, Message, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
import logging
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update
from app.config import settings
from app.models import Payment, User
from app.services.user_service import activate_premium, deactivate_premium
from app.services.referral_service import add_referral_on_payment
from app.services.yookassa_service import create_sbp_payment
from app.database import get_db
from app.states import SurveyStates
from app.keyboards import get_payment_keyboard, get_main_keyboard
from datetime import datetime

router = Router()
"""Роутер для обработки платежей."""

logger = logging.getLogger(__name__)


@router.callback_query(F.data == "payment_start")
async def start_payment(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Обработка начала процесса оплаты.
    
    Отправляет инвойс для оплаты premium доступа через Telegram Payments.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки оплаты
        bot (Bot): Экземпляр бота для отправки сообщений
        state (FSMContext): Контекст FSM для сохранения состояния
    """
    user_id = callback.from_user.id
    
    # Проверяем наличие PROVIDER_TOKEN
    if not settings.PROVIDER_TOKEN:
        logger.error("PROVIDER_TOKEN не настроен в конфигурации")
        await callback.answer("Ошибка: платежи не настроены. Обратитесь к администратору.", show_alert=True)
        return
    
    price_rub = settings.PREMIUM_PRICE // 100
    
    # Сохраняем состояние для обработки после оплаты
    data = await state.get_data()
    pending_roadmap = data.get("pending_roadmap", False)
    await state.update_data(pending_roadmap=pending_roadmap)
    
    try:
        invoice_params = {
            "chat_id": callback.message.chat.id,
            "title": "Premium доступ",
            "description": (
                "Premium включает:\n"
                "- Персональный роадмап достижения цели\n"
                "- Ежедневные задания от ИИ-коуча\n"
                "- Обратная связь по отчетам\n"
                "- Трекинг прогресса"
            ),
            "payload": f"premium_{user_id}_{int(datetime.utcnow().timestamp())}",
            "provider_token": settings.PROVIDER_TOKEN,
            "currency": "RUB",
            "prices": [LabeledPrice(label="Premium доступ (1 месяц)", amount=settings.PREMIUM_PRICE)],
            "start_parameter": f"premium-{user_id}",
            "photo_url": None,
            "need_name": False,
            "need_phone_number": False,
            "need_email": False,
            "need_shipping_address": False,
            "send_phone_number_to_provider": False,
            "send_email_to_provider": False,
            "is_flexible": False
        }
        
        # Логируем параметры (без provider_token для безопасности)
        logger.info(f"Отправка инвойса для пользователя {user_id}. Параметры: { {k: v for k, v in invoice_params.items() if k != 'provider_token'} }")
        
        await bot.send_invoice(**invoice_params)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при отправке инвойса для пользователя {user_id}: {e}", exc_info=True)
        await callback.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "payment_sbp_start")
async def start_sbp_payment(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Обработка начала процесса оплаты через СБП (YooKassa).
    
    Создает платеж через YooKassa API с методом оплаты СБП и отправляет
    пользователю ссылку для оплаты.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки оплаты СБП
        bot (Bot): Экземпляр бота для отправки сообщений
        state (FSMContext): Контекст FSM для сохранения состояния
    """
    user_id = callback.from_user.id
    
    # Проверяем наличие YooKassa credentials
    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        logger.error("YooKassa credentials не настроены в конфигурации")
        await callback.answer("Ошибка: платежи через СБП не настроены. Обратитесь к администратору.", show_alert=True)
        return
    
    # Сохраняем состояние для обработки после оплаты
    data = await state.get_data()
    pending_roadmap = data.get("pending_roadmap", False)
    await state.update_data(pending_roadmap=pending_roadmap)
    
    try:
        # Сохраняем message_id и chat_id для последующего удаления сообщения
        message_id = callback.message.message_id
        chat_id = callback.message.chat.id
        
        # Создаем платеж через YooKassa с message_id в metadata
        payment_data = await create_sbp_payment(
            amount=settings.PREMIUM_PRICE,
            user_id=user_id,
            description="Premium доступ - Персональный роадмап, ежедневные задания, обратная связь",
            message_id=message_id,
            chat_id=chat_id
        )
        
        if not payment_data or not payment_data.get("confirmation_url"):
            logger.error(f"Не удалось создать платеж YooKassa для пользователя {user_id}")
            await callback.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)
            return
        
        # Сохраняем payment_id в состоянии для последующей обработки
        await state.update_data(yookassa_payment_id=payment_data["id"])
        
        # Создаем клавиатуру с кнопкой для оплаты
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить через СБП", url=payment_data["confirmation_url"])],
            [InlineKeyboardButton(text="Отменить", callback_data="payment_sbp_cancel")]
        ])
        
        price_rub = settings.PREMIUM_PRICE // 100
        await callback.message.edit_text(
            f"Оплата Premium доступа через СБП\n\n"
            f"Сумма: {price_rub} руб.\n\n"
            f"Нажми на кнопку ниже, чтобы перейти к оплате.\n"
            f"После успешной оплаты premium доступ будет активирован автоматически.",
            reply_markup=keyboard
        )
        await callback.answer()
        
        logger.info(f"Создан платеж YooKassa {payment_data['id']} для пользователя {user_id}, message_id={message_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при создании платежа YooKassa для пользователя {user_id}: {e}", exc_info=True)
        await callback.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "payment_sbp_cancel")
async def cancel_sbp_payment(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Обработка отмены платежа через СБП.
    
    Возвращает пользователя к экрану выбора способа оплаты.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки отмены
        bot (Bot): Экземпляр бота для отправки сообщений
        state (FSMContext): Контекст FSM
    """
    from app.services.user_service import is_premium_active
    
    user_id = callback.from_user.id
    price_rub = settings.PREMIUM_PRICE // 100
    
    # Очищаем сохраненный payment_id
    await state.update_data(yookassa_payment_id=None)
    
    async for session in get_db():
        premium_active = await is_premium_active(session, user_id)
        
        await callback.answer("Отменено")
        
        if premium_active:
            await callback.message.edit_text(
                "У тебя уже есть Premium доступ!\n\n"
                "Ты можешь пользоваться всеми функциями бота.",
                reply_markup=get_payment_keyboard(has_premium=True)
            )
        else:
            await callback.message.edit_text(
                f"Premium доступ\n\n"
                f"Premium включает:\n"
                f"- Персональный роадмап достижения цели\n"
                f"- Ежедневные задания от ИИ-коуча\n"
                f"- Обратная связь по отчетам\n"
                f"- Трекинг прогресса\n\n"
                f"Стоимость: {price_rub} руб./месяц",
                reply_markup=get_payment_keyboard(has_premium=False)
            )
        break


@router.callback_query(F.data == "subscription_cancel")
async def cancel_subscription(callback: CallbackQuery, bot: Bot):
    """Обработка нажатия кнопки отключения подписки - показывает подтверждение.
    
    Показывает предупреждение и запрашивает подтверждение перед отключением подписки.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки отключения
        bot (Bot): Экземпляр бота для отправки сообщений
    """
    from app.keyboards import get_subscription_cancel_confirmation_keyboard
    
    await callback.answer()
    await callback.message.edit_text(
        "Ты уверен, что хочешь отключить подписку?\n\n"
        "Подписка будет остановлена, и ты потеряешь доступ к:\n"
        "- Персональному роадмапу\n"
        "- Ежедневным заданиям\n"
        "- Обратной связи по отчетам\n"
        "- Трекингу прогресса\n\n"
        "Для продолжения работы нужно будет активировать подписку снова.",
        reply_markup=get_subscription_cancel_confirmation_keyboard()
    )


@router.callback_query(F.data == "subscription_cancel_confirm")
async def confirm_subscription_cancel(callback: CallbackQuery, bot: Bot):
    """Обработка подтверждения отключения подписки (мгновенный снос).
    
    Деактивирует premium доступ пользователя немедленно после подтверждения.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки подтверждения
        bot (Bot): Экземпляр бота для отправки сообщений
    """
    user_id = callback.from_user.id
    
    async for session in get_db():
        try:
            # Деактивируем premium
            await deactivate_premium(session, user_id)
            
            await callback.message.edit_text(
                "Подписка отключена\n\n"
                "Premium доступ деактивирован. Для продолжения работы активируй подписку снова."
            )
            await callback.answer("Подписка отключена")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при отключении подписки для пользователя {user_id}: {e}", exc_info=True)
            await callback.message.edit_text(
                "Произошла ошибка при отключении подписки. Попробуй позже."
            )
            await callback.answer("Ошибка", show_alert=True)
        break


@router.callback_query(F.data == "subscription_cancel_cancel")
async def cancel_subscription_cancel(callback: CallbackQuery, bot: Bot):
    """Обработка отмены отключения подписки.
    
    Возвращает пользователя к экрану оплаты без изменений.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки отмены
        bot (Bot): Экземпляр бота для отправки сообщений
    """
    from app.keyboards import get_payment_keyboard
    from app.config import settings
    from app.services.user_service import is_premium_active
    from app.database import get_db
    
    user_id = callback.from_user.id
    price_rub = settings.PREMIUM_PRICE // 100
    
    async for session in get_db():
        premium_active = await is_premium_active(session, user_id)
        
        await callback.answer("Отменено")
        
        if premium_active:
            await callback.message.edit_text(
                "У тебя уже есть Premium доступ!\n\n"
                "Ты можешь пользоваться всеми функциями бота.",
                reply_markup=get_payment_keyboard(has_premium=True)
            )
        else:
            await callback.message.edit_text(
                f"Premium доступ\n\n"
                f"Premium включает:\n"
                f"- Персональный роадмап достижения цели\n"
                f"- Ежедневные задания от ИИ-коуча\n"
                f"- Обратная связь по отчетам\n"
                f"- Трекинг прогресса\n\n"
                f"Стоимость: {price_rub} руб./месяц",
                reply_markup=get_payment_keyboard(has_premium=False)
            )
        break


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    """Валидация платежа перед подтверждением.
    
    Проверяет корректность платежа и автоматически одобряет его.
    
    Args:
        pre_checkout_query (PreCheckoutQuery): Запрос на валидацию платежа
        bot (Bot): Экземпляр бота
    """
    user_id = pre_checkout_query.from_user.id
    
    # Проверяем сумму платежа
    if pre_checkout_query.total_amount != settings.PREMIUM_PRICE:
        logger.warning(f"Неверная сумма платежа для пользователя {user_id}: {pre_checkout_query.total_amount} вместо {settings.PREMIUM_PRICE}")
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Неверная сумма платежа"
        )
        return
    
    # Проверяем валюту
    if pre_checkout_query.currency != "RUB":
        logger.warning(f"Неверная валюта платежа для пользователя {user_id}: {pre_checkout_query.currency}")
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Поддерживается только валюта RUB"
        )
        return
    
    # Одобряем платеж
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    logger.info(f"Платеж одобрен для пользователя {user_id}")


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot, state: FSMContext):
    """Обработка успешного платежа.
    
    Сохраняет платеж в БД, активирует premium доступ, повышает уровень
    и обрабатывает реферальную систему.
    
    Args:
        message (Message): Сообщение с успешным платежом
        bot (Bot): Экземпляр бота
        state (FSMContext): Контекст FSM для проверки состояния
    """
    user_id = message.from_user.id
    payment = message.successful_payment
    
    logger.info(f"Обработка успешного платежа для пользователя {user_id}, сумма: {payment.total_amount}")
    
    async for session in get_db():
        try:
            # Сохраняем платеж в БД
            db_payment = Payment(
                user_id=user_id,
                payment_id=payment.telegram_payment_charge_id,
                amount=payment.total_amount,
                status="completed"
            )
            session.add(db_payment)
            
            # Активируем premium на 1 месяц
            await activate_premium(session, user_id, months=1)
            
            # Повышаем уровень до 1 при первой оплате
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            
            if user and user.level == 0:
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
                logger.info(f"Активирован premium для реферера {referrer_id} за оплату пользователя {user_id}")
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при обработке платежа для пользователя {user_id}: {e}", exc_info=True)
            await session.rollback()
            await message.answer(
                "Произошла ошибка при активации premium доступа.\n"
                "Платеж прошел успешно, но активация не завершена.\n"
                "Обратитесь к администратору."
            )
            break
    
    # Проверяем, нужно ли продолжить генерацию роадмапа
    data = await state.get_data()
    pending_roadmap = data.get("pending_roadmap", False)
    
    if pending_roadmap:
        # Убираем флаг и продолжаем генерацию роадмапа
        await state.update_data(pending_roadmap=False)
        await message.answer("Premium доступ активирован! Генерирую роадмап...")
        
        # Импортируем функцию генерации роадмапа
        from app.handlers.survey import generate_roadmap_after_payment
        await generate_roadmap_after_payment(message, state, bot)
    else:
        # Проверяем, прошел ли пользователь опрос
        async for session in get_db():
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            
            if user and (not user.goal_3months and not user.roadmap):
                # Пользователь еще не прошел опрос - начинаем опрос
                from app.keyboards import get_gender_keyboard, get_main_keyboard
                from app.states import SurveyStates
                
                await state.set_state(SurveyStates.gender)
                await message.answer(
                    "Premium доступ активирован!\n\n"
                    "Привет! Ты попал в пространство развития Progressus.\n\n"
                    "Progressus - твой лучший персональный наставник.\n\n"
                    "- Топовые ролевые модели\n"
                    "- Персональные задания\n\n"
                    "Именно здесь ты реализуешь весь свой потенциал, но для начала "
                    "давай пройдем небольшой опрос, чтобы лучше тебя понять.\n\n"
                    "Твой пол?",
                    reply_markup=get_gender_keyboard()
                )
                await message.answer(
                    "",
                    reply_markup=get_main_keyboard()
                )
            else:
                # Пользователь уже прошел опрос
                await message.answer(
                    "Premium доступ активирован!\n\n"
                    "Теперь тебе доступен весь функционал бота!"
                )
            break


@router.callback_query(F.data == "promo_code_enter")
async def enter_promo_code(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки "Ввести промокод".
    
    Переводит пользователя в состояние ввода промокода.
    
    Args:
        callback (CallbackQuery): Callback запрос от нажатия кнопки
        state (FSMContext): Контекст FSM
    """
    await callback.answer()
    await state.set_state(SurveyStates.promo_code)
    
    await callback.message.edit_text(
        "Введи промокод:\n\n"
        "Напиши промокод для активации premium доступа.",
        reply_markup=None
    )


@router.message(SurveyStates.promo_code)
async def process_promo_code(message: Message, state: FSMContext):
    """Обработка введенного промокода.
    
    Проверяет промокод и активирует premium доступ при успешной проверке.
    
    Args:
        message (Message): Сообщение с промокодом
        state (FSMContext): Контекст FSM
    """
    user_id = message.from_user.id
    user_text = message.text.strip()
    
    # Проверяем команды выхода
    if user_text.lower() in ["отмена", "меню", "/menu", "menu", "назад"]:
        await state.clear()
        from app.config import settings
        from app.services.user_service import is_premium_active
        
        price_rub = settings.PREMIUM_PRICE // 100
        
        async for session in get_db():
            premium_active = await is_premium_active(session, user_id)
            
            if premium_active:
                await message.answer(
                    "У тебя уже есть Premium доступ!\n\n"
                    "Ты можешь пользоваться всеми функциями бота.",
                    reply_markup=get_payment_keyboard(has_premium=True)
                )
            else:
                await message.answer(
                    f"Premium доступ\n\n"
                    f"Premium включает:\n"
                    f"- Персональный роадмап достижения цели\n"
                    f"- Ежедневные задания от ИИ-коуча\n"
                    f"- Обратная связь по отчетам\n"
                    f"- Трекинг прогресса\n\n"
                    f"Стоимость: {price_rub} руб./месяц",
                    reply_markup=get_payment_keyboard(has_premium=False)
                )
            break
        return
    
    promo_code = user_text.upper()
    
    # Проверяем промокод
    if promo_code == "FREEADMIN":
        async for session in get_db():
            try:
                # Активируем premium на длительный срок (например, 10 лет для админов)
                await activate_premium(session, user_id, months=120)
                
                await session.commit()
                
                await message.answer(
                    "Промокод активирован!\n\n"
                    "Premium доступ активирован на длительный срок.\n"
                    "Теперь тебе доступен веь функционал бота!",
                    reply_markup=get_main_keyboard()
                )
                
                logger.info(f"Промокод FREEADMIN активирован для пользователя {user_id}")
                
            except Exception as e:
                logger.error(f"Ошибка при активации промокода для пользователя {user_id}: {e}", exc_info=True)
                await message.answer(
                    "Произошла ошибка при активации промокода. Попробуй позже.",
                    reply_markup=get_main_keyboard()
                )
            break
        
        await state.clear()
    else:
        # Неверный промокод
        await message.answer(
            "Неверный промокод.\n\n"
            "Проверь правильность ввода и попробуй еще раз.\n"
            "Для отмены напиши 'Отмена' или 'Назад'.",
            reply_markup=get_main_keyboard()
        )

