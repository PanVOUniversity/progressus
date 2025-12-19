"""Handler для главного меню бота.

Модуль обрабатывает показ главного меню и обработку кнопок меню.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.keyboards import get_main_menu_keyboard, get_main_keyboard
from app.database import get_db
from app.services.user_service import get_or_create_user
from app.models import User
from app.states import SurveyStates
from sqlalchemy import select

router = Router()
"""Роутер для обработки главного меню."""


async def show_main_menu(message: Message, state: FSMContext = None, user: User = None):
    """Показывает главное меню пользователю.
    
    Сохраняет текущее состояние FSM перед показом меню, чтобы можно было вернуться к предыдущему диалогу.
    
    Args:
        message (Message): Сообщение от пользователя
        state (FSMContext, optional): Контекст FSM для сохранения состояния
        user (User, optional): Объект пользователя из БД. Если не передан, будет получен из БД.
    """
    user_id = message.from_user.id
    
    # Сохраняем текущее состояние перед показом меню
    if state:
        current_state = await state.get_state()
        current_data = await state.get_data()
        if current_state and current_state != SurveyStates.consultation:
            # Сохраняем состояние и данные для восстановления
            await state.update_data(
                previous_state=str(current_state),
                previous_state_data=current_data.copy()
            )
    
    # Если пользователь не передан, получаем из БД
    if user is None:
        async for session in get_db():
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            break
    
    # Получаем имя пользователя
    user_name = user.name if user and user.name else message.from_user.first_name or "друг"
    
    # Формируем текст меню согласно дизайну
    menu_text = f"👋 Привет, {user_name}!\n\n"
    menu_text += "📈 Progressus - твой лучший персональный наставник.\n\n"
    menu_text += "✨ Топовые ролевые модели\n"
    menu_text += "📝 Персональные задания\n\n"
    menu_text += "💰 Приглашайте друзей и получайте 30% с каждого!\n"
    menu_text += "🎁 Приглашенные получат 3 дня доступа бесплатно!"
    
    # Отправляем сообщение с inline кнопками меню под текстом
    await message.answer(
        menu_text,
        reply_markup=get_main_menu_keyboard()  # Inline кнопки под сообщением
    )
    # Отправляем постоянную клавиатуру отдельным сообщением
    await message.answer(
        "",
        reply_markup=get_main_keyboard()  # Постоянная клавиатура под клавиатурой
    )


@router.message(F.text.in_(["Меню", "/menu", "menu"]))
async def cmd_menu(message: Message, state: FSMContext):
    """Обработка команды /menu или кнопки "Меню".
    
    Показывает главное меню пользователю, сохраняя текущее состояние.
    
    Args:
        message (Message): Сообщение от пользователя
        state (FSMContext): Контекст FSM
    """
    # Показываем меню (состояние сохраняется внутри функции)
    await show_main_menu(message, state)


@router.callback_query(F.data == "menu_consultation")
async def cmd_consultation(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки "Свободная консультация".
    
    Переводит пользователя в режим консультации, где бот отвечает на вопросы
    в стиле выбранного наставника.
    
    Args:
        callback (CallbackQuery): Callback от inline кнопки
        state (FSMContext): Контекст FSM
    """
    user_id = callback.from_user.id
    message = callback.message
    
    # Получаем пользователя и проверяем, есть ли у него выбранный персонаж
    async for session in get_db():
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.personality:
            await callback.answer("Сначала пройди опрос через /start, чтобы выбрать своего наставника.")
            await message.edit_text(
                "💬 Свободная консультация\n\n"
                "Сначала пройди опрос через /start, чтобы выбрать своего наставника.",
                reply_markup=None
            )
            await message.answer(
                "",
                reply_markup=get_main_keyboard()
            )
            break
        
        # Устанавливаем состояние консультации
        await state.set_state(SurveyStates.consultation)
        await callback.answer()
        await message.edit_text(
            "💬 Свободная консультация\n\n"
            "Задай мне любой вопрос, и я помогу тебе разобраться в стиле твоего наставника.\n\n"
            "Напиши свой вопрос:",
            reply_markup=None
        )
        await message.answer(
            reply_markup=get_main_keyboard()
        )
        break


@router.message(SurveyStates.consultation)
async def process_consultation(message: Message, state: FSMContext):
    """Обработка текстовых сообщений в режиме консультации.
    
    Отвечает на вопросы пользователя в стиле выбранного наставника.
    
    Args:
        message (Message): Сообщение с вопросом от пользователя
        state (FSMContext): Контекст FSM
    """
    user_id = message.from_user.id
    user_question = message.text
    
    # Проверяем, не является ли это командой меню или рестарта
    if user_question in ["Меню", "/menu", "menu", "Свободная консультация", "Задания", "Помощь", "Оплата", "Реферальная программа", "🔄 Рестарт", "/restart"]:
        # Если это рестарт, выходим из консультации и позволяем обработчику рестарта обработать
        if user_question in ["🔄 Рестарт", "/restart"]:
            await state.clear()
            return  # Позволяем обработчику рестарта обработать сообщение
        await state.clear()
        await show_main_menu(message, state)
        return
    
    # Получаем пользователя и его персонажа
    async for session in get_db():
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.personality:
            await message.answer(
                "Сначала пройди опрос через /start, чтобы выбрать своего наставника.",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            break
        
        # Генерируем ответ в стиле персонажа
        from app.gpt import client, clean_markdown
        from app.prompts import get_personality_prompt
        from app.config import settings
        
        personality_data = get_personality_prompt(user.personality)
        
        # Показываем, что бот думает
        await message.answer("💭 Думаю...")
        
        try:
            prompt = f"""Пользователь задал вопрос: {user_question}

Ответь на этот вопрос в своем стиле. Будь полезным, мотивирующим и конкретным.
Если вопрос не по теме развития или неясен, вежливо уточни или перенаправь разговор.

Отвечай кратко, по делу, в своем стиле. Не используй звездочки или markdown форматирование."""
            
            response = await client.chat.completions.create(
                model=settings.OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": personality_data["system_prompt"]},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            answer = clean_markdown(answer)
            
            await message.answer(answer, reply_markup=get_main_keyboard())
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при генерации ответа консультации: {e}", exc_info=True)
            await message.answer(
                "Произошла ошибка при генерации ответа. Попробуй еще раз или напиши /menu для возврата в меню.",
                reply_markup=get_main_keyboard()
            )
        
        break


@router.callback_query(F.data == "menu_tasks")
async def cmd_tasks(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки "Задания".
    
    Показывает текущее активное ДЗ пользователя и переводит в режим ожидания отчета.
    
    Args:
        callback (CallbackQuery): Callback от inline кнопки
        state (FSMContext): Контекст FSM
    """
    user_id = callback.from_user.id
    message = callback.message
    
    async for session in get_db():
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await callback.answer("Сначала пройди опрос через /start")
            await message.edit_text(
                "Сначала пройди опрос через /start",
                reply_markup=None
            )
            await message.answer(
                "",
                reply_markup=get_main_keyboard()
            )
            break
        
        # Проверяем активность премиума
        from app.services.user_service import is_premium_active
        if not await is_premium_active(session, user_id):
            await callback.answer("Для работы с заданиями нужен Premium доступ")
            await message.edit_text(
                "Для работы с заданиями нужен Premium доступ. Активируй его через /start",
                reply_markup=None
            )
            await message.answer(
                "",
                reply_markup=get_main_keyboard()
            )
            break
        
        await callback.answer()
        
        if user.current_homework:
            # Очищаем состояние FSM, чтобы бот мог принимать отчеты
            await state.clear()
            
            # Проверяем, требуется ли переделка
            if user.homework_needs_revision:
                await message.edit_text(
                    f"📝 Твое текущее задание (уровень {user.level}):\n\n{user.current_homework}\n\n"
                    "⚠️ Это задание требует переделки. Выполни его с учетом правок и отправь отчет текстом.",
                    reply_markup=None
                )
            else:
                await message.edit_text(
                    f"📝 Твое текущее задание (уровень {user.level}):\n\n{user.current_homework}\n\n"
                    "Выполни задание и отправь отчет текстом. Я оценю твою работу и дам обратную связь! 💪",
                    reply_markup=None
                )
            await message.answer(
                "",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.edit_text(
                "У тебя пока нет активного задания.\n\n"
                "Пройди опрос через /start, чтобы получить первое персональное задание!",
                reply_markup=None
            )
            await message.answer(
                "",
                reply_markup=get_main_keyboard()
            )
        break


@router.callback_query(F.data == "menu_help")
async def cmd_help(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки "Помощь".
    
    Args:
        callback (CallbackQuery): Callback от inline кнопки
        state (FSMContext): Контекст FSM
    """
    help_text = "❓ Помощь\n\n"
    help_text += "📋 Основные команды:\n"
    help_text += "/start - Начать работу с ботом\n"
    help_text += "/menu или кнопка 'Меню' - Главное меню\n"
    help_text += "/ref - Получить реферальную ссылку\n"
    help_text += "/restart - Рестарт бота (сброс данных)\n\n"
    help_text += "💡 Как пользоваться:\n"
    help_text += "1. Пройди опрос через /start\n"
    help_text += "2. Получи персональное задание\n"
    help_text += "3. Выполни задание и отправь отчет\n"
    help_text += "4. Получи обратную связь и новое задание\n\n"
    help_text += "Если у тебя есть вопросы, напиши их здесь!"
    
    await callback.answer()
    await callback.message.edit_text(help_text, reply_markup=None)
    await callback.message.answer(
        "",
        reply_markup=get_main_keyboard()
    )


@router.callback_query(F.data == "menu_payment")
async def cmd_payment(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки "Оплата".
    
    Показывает информацию о premium доступе и возможность оплаты.
    
    Args:
        callback (CallbackQuery): Callback от inline кнопки
        state (FSMContext): Контекст FSM
    """
    from app.keyboards import get_payment_keyboard
    from app.config import settings
    from app.services.user_service import is_premium_active
    from app.database import get_db
    
    user_id = callback.from_user.id
    message = callback.message
    price_rub = settings.PREMIUM_PRICE // 100
    
    async for session in get_db():
        premium_active = await is_premium_active(session, user_id)
        
        await callback.answer()
        
        if premium_active:
            await message.edit_text(
                "💎 У тебя уже есть Premium доступ!\n\n"
                "Ты можешь пользоваться всеми функциями бота.",
                reply_markup=None
            )
        else:
            await message.edit_text(
                f"💎 Premium доступ\n\n"
                f"Premium включает:\n"
                f"✅ Персональный роадмап достижения цели\n"
                f"✅ Ежедневные задания от ИИ-коуча\n"
                f"✅ Обратная связь по отчетам\n"
                f"✅ Трекинг прогресса\n\n"
                f"Стоимость: {price_rub} руб./месяц",
                reply_markup=get_payment_keyboard()
            )
        await message.answer(
            reply_markup=get_main_keyboard()
        )
        break


@router.callback_query(F.data == "menu_referral")
async def cmd_referral_program(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки "Реферальная программа".
    
    Показывает информацию о реферальной программе и ссылку.
    
    Args:
        callback (CallbackQuery): Callback от inline кнопки
        state (FSMContext): Контекст FSM
    """
    from app.services.referral_service import generate_referral_link, get_referral_stats
    from app.keyboards import get_share_referral_keyboard
    from app.database import get_db
    
    user_id = callback.from_user.id
    message = callback.message
    
    # Получаем username бота
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username
    
    # Генерируем ссылку
    referral_link = generate_referral_link(user_id, bot_username)
    
    # Получаем статистику
    async for session in get_db():
        stats = await get_referral_stats(session, user_id)
        
        # Формируем сообщение
        stats_text = (
            f"📊 Статистика рефералов:\n"
            f"• Всего рефералов: {stats['total_referrals']}\n"
            f"• Оплатили премиум: {stats['paid_referrals']}\n"
        )
        
        if stats['referrals_to_premium'] > 0:
            stats_text += (
                f"• Рефералов до премиума: {stats['referrals_to_premium']}\n"
            )
        
        referral_text = (
            f"💰 Реферальная программа\n\n"
            f"Приглашай друзей и получай 30% с каждого платежа!\n\n"
            f"Твоя реферальная ссылка:\n`{referral_link}`\n\n"
            f"{stats_text}\n"
            f"🎁 Приглашенные получат 3 дня Premium доступа бесплатно!"
        )
        
        await callback.answer()
        await message.edit_text(
            referral_text,
            reply_markup=get_share_referral_keyboard(referral_link),
            parse_mode="Markdown"
        )
        await message.answer(
            reply_markup=get_main_keyboard()
        )
        break



