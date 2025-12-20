"""Handler для команды /start.

Модуль обрабатывает команду /start и инициализирует процесс
взаимодействия пользователя с ботом: проверяет согласие на ПД,
обрабатывает реферальные ссылки и запускает опросник.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.states import SurveyStates
from app.services.user_service import get_or_create_user
from app.services.referral_service import process_referral
from app.services.survey_state_service import restore_survey_state, clear_survey_state
from app.keyboards import get_privacy_consent_keyboard, get_gender_keyboard, get_main_keyboard, get_values_keyboard, get_development_spheres_keyboard, get_role_model_keyboard
from app.database import get_db
from app.handlers.menu import show_main_menu
import logging

logger = logging.getLogger(__name__)

router = Router()
"""Роутер для обработки команды /start."""


async def restore_survey_from_db(message: Message, state: FSMContext) -> bool:
    """Восстанавливает состояние опроса из БД.
    
    Args:
        message (Message): Сообщение от пользователя
        state (FSMContext): Контекст FSM
        
    Returns:
        bool: True если состояние было восстановлено, False иначе
    """
    user_id = message.from_user.id
    
    async for session in get_db():
        saved_state = await restore_survey_state(session, user_id)
        
        if saved_state and saved_state.get("state") and saved_state.get("data"):
            try:
                # Парсим состояние (формат: "SurveyStates:gender")
                state_str = saved_state["state"]
                state_data = saved_state["data"]
                
                if ":" in state_str:
                    state_group, state_name = state_str.split(":", 1)
                    if state_group == "SurveyStates":
                        state_obj = getattr(SurveyStates, state_name, None)
                        if state_obj:
                            # Восстанавливаем состояние и данные
                            await state.set_state(state_obj)
                            for key, value in state_data.items():
                                await state.update_data({key: value})
                            
                            # Показываем соответствующее сообщение в зависимости от состояния
                            if state_name == "gender":
                                await message.answer(
                                    "Продолжаем опрос. Твой пол?",
                                    reply_markup=get_gender_keyboard()
                                )
                            elif state_name == "age":
                                await message.answer("Сколько тебе лет? (Напиши число)")
                            elif state_name == "name":
                                name = state_data.get("name", "")
                                if name:
                                    await message.answer(f"Привет, {name}! Продолжаем опрос.")
                                else:
                                    await message.answer("Как тебя зовут? (Напиши свое имя)")
                            elif state_name == "values":
                                await message.answer(
                                    "Выбери 3 своих основных ценности в жизни:\n"
                                    "(Можно выбрать несколько, затем нажми '✅ Готово')",
                                    reply_markup=get_values_keyboard()
                                )
                            elif state_name == "development_spheres":
                                await message.answer(
                                    "Выбери сферы, в которых хочешь развиваться:\n"
                                    "(Можно выбрать несколько, затем нажми '✅ Готово')",
                                    reply_markup=get_development_spheres_keyboard()
                                )
                            elif state_name == "detailed_questions":
                                detailed_questions = state_data.get("detailed_questions", [])
                                current_index = state_data.get("current_question_index", 0)
                                if detailed_questions and current_index < len(detailed_questions):
                                    current_question = detailed_questions[current_index]
                                    # Поддерживаем как новый формат (словарь), так и старый (строка)
                                    if isinstance(current_question, dict):
                                        question_text = current_question.get("question", "")
                                    else:
                                        question_text = current_question
                                    await message.answer(question_text)
                            elif state_name == "role_model":
                                await message.answer(
                                    "Отлично! Теперь выбери свою ролевую модель:",
                                    reply_markup=get_role_model_keyboard()
                                )
                            elif state_name == "goal_3months":
                                await message.answer(
                                    "Отлично! Теперь напиши свою цель на ближайшие 3 месяца:\n"
                                    "(Опиши конкретно, что ты хочешь достичь)"
                                )
                            else:
                                await message.answer("Продолжаем опрос...")
                            
                            await message.answer(
                                "",
                                reply_markup=get_main_keyboard()
                            )
                            return True
            except Exception as e:
                logger.error(f"Ошибка восстановления состояния: {e}", exc_info=True)
                # Очищаем некорректное состояние
                await clear_survey_state(session, user_id)
        break
    
    return False


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start без реферальной ссылки.
    
    Проверяет, дал ли пользователь согласие на обработку ПД.
    Если да - переходит к опроснику, если нет - показывает
    запрос на согласие.
    
    Args:
        message (Message): Сообщение от пользователя с командой /start
        state (FSMContext): Контекст конечного автомата для хранения состояния
    """
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Получаем или создаем пользователя
    async for session in get_db():
        user = await get_or_create_user(session, user_id, username)
        
        # Проверяем, дал ли пользователь согласие на ПД
        if user.privacy_consent_accepted:
            # Проверяем, прошел ли пользователь опрос (есть цель или роадмап)
            if user.goal_3months or user.roadmap:
                # Пользователь уже прошел опрос - показываем меню
                await state.clear()
                await clear_survey_state(session, user_id)  # Очищаем сохраненное состояние
                await show_main_menu(message, state, user)
            else:
                # Пытаемся восстановить состояние опроса из БД
                restored = await restore_survey_from_db(message, state)
                if not restored:
                    # Состояние не восстановлено - начинаем опрос с начала
                    await state.set_state(SurveyStates.gender)
            await message.answer(
                        "👋 Привет! Ты попал в пространство развития Progressus.\n\n"
                        "📈 Progressus - твой лучший персональный наставник.\n\n"
                        "✨ Топовые ролевые модели\n"
                        "📝 Персональные задания\n\n"
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
            # Показываем согласие на ПД
            await state.set_state(SurveyStates.privacy_consent)
            await message.answer(
                "👋 Привет! Ты попал в пространство развития Progressus.\n\n"
                "📈 Progressus - это бот для твоего личного развития. "
                "Наша задача - добиться твоего ежедневного роста. "
                "Каждый день ты будешь в общении с нами получать рекомендации "
                "исходя из твоих целей и навыков.\n\n"
                "✨ Топовые ролевые модели\n"
                "📝 Персональные задания\n\n"
                "Для работы бота нам необходимо твое согласие на обработку персональных данных.",
                reply_markup=get_privacy_consent_keyboard()
            )
        break


@router.message(F.text.startswith("/start"))
async def cmd_start_with_ref(message: Message, state: FSMContext):
    """Обработка команды /start с реферальной ссылкой.
    
    Обрабатывает команду /start с реферальным параметром (формат: /start ref123456).
    Парсит ID реферера и обрабатывает реферальную связь перед запуском опросника.
    
    Args:
        message (Message): Сообщение от пользователя с командой /start и реферальным параметром
        state (FSMContext): Контекст конечного автомата для хранения состояния
        
    Note:
        Реферальная ссылка имеет формат: /start ref{user_id}
        Реферальная связь устанавливается только если referrer_id != user_id
    """
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Парсим реферальную ссылку
    referrer_id = None
    if "ref" in message.text:
        try:
            # Формат: /start ref123456
            ref_part = message.text.split("ref")[-1]
            referrer_id = int(ref_part)
        except (ValueError, IndexError):
            pass
    
    # Получаем или создаем пользователя
    async for session in get_db():
        user = await get_or_create_user(session, user_id, username)
        
        # Обрабатываем рефералку
        if referrer_id and referrer_id != user_id:
            await process_referral(session, user_id, referrer_id)
        
        # Проверяем согласие на ПД
        if user.privacy_consent_accepted:
            # Проверяем, прошел ли пользователь опрос (есть цель или роадмап)
            if user.goal_3months or user.roadmap:
                # Пользователь уже прошел опрос - показываем меню
                await state.clear()
                await clear_survey_state(session, user_id)  # Очищаем сохраненное состояние
                await show_main_menu(message, state, user)
            else:
                # Пытаемся восстановить состояние опроса из БД
                restored = await restore_survey_from_db(message, state)
                if not restored:
                    # Состояние не восстановлено - начинаем опрос с начала
                    await state.set_state(SurveyStates.gender)
            await message.answer(
                        "👋 Привет! Ты попал в пространство развития Progressus.\n\n"
                        "📈 Progressus - твой лучший персональный наставник.\n\n"
                        "✨ Топовые ролевые модели\n"
                        "📝 Персональные задания\n\n"
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
            await state.set_state(SurveyStates.privacy_consent)
            await message.answer(
                "👋 Привет! Ты попал в пространство развития Progressus.\n\n"
                "📈 Progressus - это бот для твоего личного развития. "
                "Наша задача - добиться твоего ежедневного роста. "
                "Каждый день ты будешь в общении с нами получать рекомендации "
                "исходя из твоих целей и навыков.\n\n"
                "✨ Топовые ролевые модели\n"
                "📝 Персональные задания\n\n"
                "Для работы бота нам необходимо твое согласие на обработку персональных данных.",
                reply_markup=get_privacy_consent_keyboard()
            )
        break
