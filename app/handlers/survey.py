"""Handlers для нового опросника согласно CJM.

Модуль содержит обработчики для всех вопросов нового опросника:
- 5 базовых вопросов (пол, возраст, имя, ценности, сферы)
- 5 развернутых вопросов от GPT
- Выбор ролевой модели
- Цель на 3 месяца
- Генерация роадмапа
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.states import SurveyStates
from app.keyboards import (
    get_gender_keyboard, get_values_keyboard, get_development_spheres_keyboard,
    get_role_model_keyboard, get_main_keyboard, get_payment_keyboard
)
from app.gpt import generate_detailed_questions, generate_roadmap, generate_first_homework, _map_role_model_to_personality
from app.models import Survey, User
from app.services.user_service import update_user_category, update_user_homework, update_user_personality, is_premium_active
from app.services.survey_state_service import save_survey_state, restore_survey_state, clear_survey_state
from app.database import get_db
from sqlalchemy import select
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = Router()
"""Роутер для обработки нового опросника."""


async def generate_roadmap_after_payment(message: Message, state: FSMContext, bot: Bot):
    """Генерирует и показывает роадмап после оплаты premium."""
    data = await state.get_data()
    goal_3months = data.get("goal_3months")
    
    if not goal_3months:
        await message.answer("Ошибка: цель не найдена. Напиши /start для начала.")
        return
    
    await message.answer("🗺️ Генерирую твой персональный роадмап достижения цели...")
    
    basic_answers = {
        "gender": data.get("gender"),
        "age": data.get("age"),
        "name": data.get("name"),
        "values": data.get("values", []),
        "development_spheres": data.get("development_spheres", [])
    }
    detailed_answers = data.get("detailed_answers", {})
    role_model = data.get("role_model", "Эндрю Тейт")
    
    try:
        roadmap = await generate_roadmap(
            goal_3months=goal_3months,
            basic_answers=basic_answers,
            detailed_answers=detailed_answers,
            role_model=role_model
        )
        
        await state.update_data(roadmap=roadmap)
        
        # Форматируем и показываем роадмап (новый формат с этапами)
        roadmap_text = f"🗺️ РОАДМАП: {goal_3months} за 3 месяца\n\n"
        
        # Показываем новый формат, если он есть
        if roadmap.get('stage_1'):
            for stage_num in [1, 2, 3, 4]:
                stage_key = f'stage_{stage_num}'
                stage = roadmap.get(stage_key, {})
                if stage.get('goal'):
                    weeks = stage.get('weeks', f'{stage_num*3-2}-{stage_num*3}')
                    roadmap_text += f"📅 ЭТАП {stage_num} (Недели {weeks})\n"
                    roadmap_text += f"   🎯 Milestone: {stage.get('goal', '')}\n"
                    
                    result = stage.get('result', '')
                    if result:
                        roadmap_text += f"   ✅ Результат: {result}\n"
                    roadmap_text += "\n"
        else:
            # Fallback на старый формат для обратной совместимости
            roadmap_text += "📅 Первая-вторая неделя: "
            roadmap_text += f"{roadmap.get('weeks_1_2', {}).get('text', 'Цель будет определена позже')}\n\n"
            
            roadmap_text += "📅 Третья-четвертая неделя: "
            roadmap_text += f"{roadmap.get('weeks_3_4', {}).get('text', 'Цель будет определена позже')}\n\n"
            
            roadmap_text += "📅 Пятая-восьмая неделя: "
            roadmap_text += f"{roadmap.get('weeks_5_8', {}).get('text', 'Цель будет определена позже')}\n\n"
            
            roadmap_text += "📅 Девятая-двенадцатая неделя: "
            roadmap_text += f"{roadmap.get('weeks_9_12', {}).get('text', 'Цель будет определена позже')}\n\n"
        
        # Добавляем финальный результат и первый шаг
        if roadmap.get('final_result'):
            roadmap_text += f"🎯 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ: {roadmap.get('final_result')}\n\n"
        
        if roadmap.get('first_step'):
            roadmap_text += f"🚀 ПЕРВЫЙ ШАГ СЕГОДНЯ: {roadmap.get('first_step')}"
        
        await message.answer(roadmap_text)
        
        # Сохраняем все данные в БД (отдельная обработка ошибок)
        await state.set_state(SurveyStates.roadmap_generation)
        
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            async for session in get_db():
                try:
                    # Сохраняем опрос
                    survey = Survey(
                        user_id=message.from_user.id,
                        basic_answers=basic_answers,
                        detailed_answers=detailed_answers,
                        detailed_questions=data.get("detailed_questions", []),
                        role_model=role_model,
                        goal_3months=goal_3months,
                        roadmap=roadmap
                    )
                    session.add(survey)
        
                    # Обновляем пользователя (объединяем все обновления в один запрос)
                    personality_key = _map_role_model_to_personality(role_model)
                    from sqlalchemy import update
                    await session.execute(
                        update(User)
                        .where(User.user_id == message.from_user.id)
                        .values(
                            personality=personality_key,
                            name=data.get("name"),
                            gender=data.get("gender"),
                            age=data.get("age"),
                            values=data.get("values", []),
                            development_spheres=data.get("development_spheres", []),
                            goal_3months=goal_3months,
                            roadmap=roadmap
                        )
                    )
                    
                    await session.commit()
                    logger.info(f"Данные успешно сохранены в БД для пользователя {message.from_user.id}")
                    break
                except Exception as inner_db_error:
                    # Откатываем транзакцию при ошибке
                    await session.rollback()
                    logger.error(f"Внутренняя ошибка БД при сохранении: {inner_db_error}", exc_info=True)
                    raise inner_db_error
        except Exception as db_error:
            # Логируем ошибку БД, но продолжаем работу (роадмап уже отправлен)
            logger.error(f"Ошибка при сохранении данных в БД: {db_error}", exc_info=True)
        
        # Генерируем первое ДЗ (отдельная обработка ошибок)
        try:
            await message.answer("📝 Генерирую твое первое персональное задание...")
            
            first_homework = await generate_first_homework(
                basic_answers=basic_answers,
                detailed_answers=detailed_answers,
                goal_3months=goal_3months,
                roadmap=roadmap,
                role_model=role_model
            )
            
            # Сохраняем первое ДЗ в БД (отдельная обработка ошибок)
            homework_saved = False
            try:
                async for session in get_db():
                    try:
                        # Сохраняем ДЗ
                        user = await update_user_homework(session, message.from_user.id, first_homework)
                        if user and user.current_homework:
                            homework_saved = True
                            logger.info(f"ДЗ успешно сохранено для пользователя {message.from_user.id}")
                        else:
                            logger.error(f"ДЗ не было сохранено для пользователя {message.from_user.id}")
                        
                        # Устанавливаем уровень 0
                        from app.services.user_service import update_user_level
                        await update_user_level(session, message.from_user.id, 0)
                        break
                    except Exception as save_error:
                        logger.error(f"Ошибка при сохранении ДЗ в БД: {save_error}", exc_info=True)
                        await session.rollback()
                        break
            except Exception as db_error:
                logger.error(f"Ошибка при подключении к БД для сохранения ДЗ: {db_error}", exc_info=True)
            
            # Отправляем ДЗ только если оно успешно сохранено
            if homework_saved:
                # Очищаем сохраненное состояние опроса, так как опрос завершен
                async for session in get_db():
                    try:
                        await clear_survey_state(session, message.from_user.id)
                        break
                    except Exception as e:
                        logger.error(f"Ошибка очистки состояния: {e}", exc_info=True)
                        break
                
                await state.set_state(SurveyStates.finish)
                await state.clear()  # Очищаем FSM состояние
                await message.answer(
                    f"📝 Твое первое персональное задание (уровень 0):\n\n{first_homework}\n\n"
                    "Выполни задание и отправь отчет текстом. Я оценю твою работу и дам обратную связь! 💪",
                    reply_markup=get_main_keyboard()
                )
            else:
                logger.error(f"Не удалось сохранить ДЗ для пользователя {message.from_user.id}, не отправляем ДЗ")
                await state.set_state(SurveyStates.finish)
                await message.answer(
                    "Произошла ошибка при сохранении задания. Попробуй написать /start еще раз.",
                    reply_markup=get_main_keyboard()
                )
        except Exception as hw_error:
            logger.error(f"Ошибка при генерации первого ДЗ: {hw_error}", exc_info=True)
            await state.set_state(SurveyStates.finish)
            await message.answer(
                "Произошла ошибка при генерации задания. Попробуй написать /start еще раз.",
                reply_markup=get_main_keyboard()
    )
        
    except Exception as e:
        logger.error(f"Ошибка при генерации роадмапа после оплаты: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при генерации роадмапа. Попробуй позже или напиши /start"
        )


@router.callback_query(F.data.startswith("gender_"))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос о поле."""
    # Проверяем, что мы в правильном состоянии (или устанавливаем его, если его нет)
    current_state = await state.get_state()
    if current_state != SurveyStates.gender:
        # Если состояние не установлено, устанавливаем его
        await state.set_state(SurveyStates.gender)
    
    gender_map = {
        "gender_male": "Мужской",
        "gender_female": "Женский"
    }
    
    gender = gender_map.get(callback.data, "Мужской")
    await state.update_data(gender=gender)
    
    # Сохраняем состояние в БД
    async for session in get_db():
        try:
            state_data = await state.get_data()
            await save_survey_state(
                session,
                callback.from_user.id,
                str(SurveyStates.age),
                state_data
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
        break
    
    await state.set_state(SurveyStates.age)
    await callback.message.edit_text(
        "Сколько тебе лет? (Напиши число)"
    )
    await callback.answer()


@router.message(SurveyStates.age)
async def process_age(message: Message, state: FSMContext):
    """Обработка ответа на вопрос о возрасте."""
    if not message.text:
        await message.answer("Пожалуйста, отправь число (твой возраст)")
        return
    
    try:
        age = int(message.text.strip())
        if age < 1 or age > 150:
            await message.answer("Пожалуйста, укажи реальный возраст (от 1 до 150)")
            return
    except ValueError:
        await message.answer("Пожалуйста, укажи возраст числом (например: 25)")
        return
    
    await state.update_data(age=age)
    
    # Сохраняем состояние в БД
    async for session in get_db():
        try:
            state_data = await state.get_data()
            await save_survey_state(
                session,
                message.from_user.id,
                str(SurveyStates.name),
                state_data
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
        break
    
    await state.set_state(SurveyStates.name)
    await message.answer("Как тебя зовут? (Напиши свое имя)")


@router.message(SurveyStates.name)
async def process_name(message: Message, state: FSMContext):
    """Обработка ответа на вопрос об имени."""
    if not message.text:
        await message.answer("Пожалуйста, отправь текст (твое имя)")
        return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, укажи свое имя (минимум 2 символа)")
        return
    
    await state.update_data(name=name)
    
    # Сохраняем состояние в БД
    async for session in get_db():
        try:
            state_data = await state.get_data()
            await save_survey_state(
                session,
                message.from_user.id,
                str(SurveyStates.values),
                state_data
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
        break
    
    data = await state.get_data()
    user_name = data.get("name", "друг")
    
    await state.set_state(SurveyStates.values)
    await message.answer(
        f"Приятно познакомиться, {user_name}! 👋\n\n"
        "Выбери 3 своих основных ценности в жизни:\n"
        "(Можно выбрать несколько, затем нажми '✅ Готово')",
        reply_markup=get_values_keyboard()
    )


# Обработка выбора ценностей
selected_values = {}  # Временное хранилище выбранных ценностей по user_id


@router.callback_query(F.data.startswith("value_"), SurveyStates.values)
async def process_value_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора ценности."""
    user_id = callback.from_user.id
    
    if user_id not in selected_values:
        selected_values[user_id] = []
    
    value_map = {
        "value_honesty": "Честность",
        "value_peace": "Спокойствие",
        "value_family": "Дружба, семья",
        "value_money": "Деньги",
        "value_power": "Власть",
        "value_care": "Забота о других",
        "value_creation": "Созидание"
    }
    
    value = value_map.get(callback.data)
    if value:
        if value in selected_values[user_id]:
            selected_values[user_id].remove(value)
        else:
            if len(selected_values[user_id]) < 3:
                selected_values[user_id].append(value)
            else:
                await callback.answer("Можно выбрать максимум 3 ценности", show_alert=True)
                return
    
    # Обновляем клавиатуру с галочками на выбранных кнопках
    count = len(selected_values[user_id])
    keyboard = get_values_keyboard(selected_values=selected_values[user_id])
    
    # Обновляем сообщение с новой клавиатурой
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка обновления клавиатуры: {e}", exc_info=True)
    
    # Показываем уведомление
    if count == 3:
        await callback.answer(f"Выбрано 3 ценности. Нажми '✅ Готово'", show_alert=False)
    else:
        await callback.answer(f"Выбрано: {count}/3", show_alert=False)


@router.callback_query(F.data == "values_done", SurveyStates.values)
async def process_values_done(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора ценностей."""
    user_id = callback.from_user.id
    
    if user_id not in selected_values or len(selected_values[user_id]) != 3:
        await callback.answer("Выбери ровно 3 ценности", show_alert=True)
        return
    
    values = selected_values[user_id]
    await state.update_data(values=values)
    del selected_values[user_id]
    
    # Сохраняем состояние в БД
    async for session in get_db():
        try:
            state_data = await state.get_data()
            await save_survey_state(
                session,
                callback.from_user.id,
                str(SurveyStates.development_spheres),
                state_data
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
        break
    
    await state.set_state(SurveyStates.development_spheres)
    await callback.message.edit_text(
        "Выбери сферы, в которых хочешь развиваться:\n"
        "(Можно выбрать несколько, затем нажми '✅ Готово')",
        reply_markup=get_development_spheres_keyboard()
    )
    await callback.answer()


# Обработка выбора сфер развития
selected_spheres = {}  # Временное хранилище выбранных сфер по user_id


@router.callback_query(F.data.startswith("sphere_"), SurveyStates.development_spheres)
async def process_sphere_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора сферы развития."""
    user_id = callback.from_user.id
    
    if user_id not in selected_spheres:
        selected_spheres[user_id] = []
    
    sphere_map = {
        "sphere_earnings": "Заработок",
        "sphere_relationships": "Отношения",
        "sphere_health": "Здоровье/Тело",
        "sphere_mind": "Разум",
        "sphere_communication": "Коммуникации"
    }
    
    sphere = sphere_map.get(callback.data)
    if sphere:
        if sphere in selected_spheres[user_id]:
            selected_spheres[user_id].remove(sphere)
        else:
            selected_spheres[user_id].append(sphere)
    
    # Обновляем клавиатуру с галочками на выбранных кнопках
    count = len(selected_spheres[user_id])
    keyboard = get_development_spheres_keyboard(selected_spheres=selected_spheres[user_id])
    
    # Обновляем сообщение с новой клавиатурой
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка обновления клавиатуры: {e}", exc_info=True)
    
    await callback.answer(f"Выбрано: {count}", show_alert=False)


@router.callback_query(F.data == "spheres_done", SurveyStates.development_spheres)
async def process_spheres_done(callback: CallbackQuery, state: FSMContext):
    """Завершение выбора сфер развития."""
    user_id = callback.from_user.id
    
    if user_id not in selected_spheres or len(selected_spheres[user_id]) == 0:
        await callback.answer("Выбери хотя бы одну сферу развития", show_alert=True)
        return
    
    spheres = selected_spheres[user_id]
    await state.update_data(development_spheres=spheres)
    del selected_spheres[user_id]
    
    # Сохраняем состояние в БД перед генерацией вопросов
    async for session in get_db():
        try:
            state_data = await state.get_data()
            await save_survey_state(
                session,
                callback.from_user.id,
                str(SurveyStates.development_spheres),
                state_data
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
        break
    
    # Генерируем развернутые вопросы от GPT
    data = await state.get_data()
    basic_answers = {
        "gender": data.get("gender"),
        "age": data.get("age"),
        "name": data.get("name"),
        "values": data.get("values", []),
        "development_spheres": data.get("development_spheres", [])
    }
    
    await callback.message.edit_text("🤔 Генерирую персонализированные вопросы для тебя...")
    
    try:
        detailed_questions = await generate_detailed_questions(basic_answers)
        
        # Проверяем, что вопросы получены
        if not detailed_questions or len(detailed_questions) == 0:
            logger.error(f"Не удалось сгенерировать вопросы для пользователя {callback.from_user.id}")
            await callback.message.edit_text(
                "Произошла ошибка при генерации вопросов. Попробуй позже или напиши /start"
            )
            return
        
        # Сохраняем вопросы в state
        await state.update_data(detailed_questions=detailed_questions)
        await state.update_data(detailed_answers={})
        await state.update_data(current_question_index=0)
        
        await state.set_state(SurveyStates.detailed_questions)
        
        # Задаем первый вопрос (отдельным сообщением, без нумерации)
        first_question = detailed_questions[0]
        if isinstance(first_question, dict):
            question_text = first_question.get("question", "")
        else:
            # Для обратной совместимости со старым форматом
            question_text = first_question
        
        await callback.message.edit_text("Отлично! Теперь ответь на несколько вопросов:")
        await callback.message.answer(question_text)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при генерации вопросов для пользователя {callback.from_user.id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "Произошла ошибка при генерации вопросов. Попробуй позже или напиши /start"
        )
    
    await callback.answer()


@router.message(SurveyStates.detailed_questions, ~F.voice)
async def process_detailed_answer(message: Message, state: FSMContext):
    """Обработка ответов на развернутые вопросы."""
    if not message.text:
        await message.answer("Пожалуйста, отправь текстовый ответ на вопрос")
        return
    
    data = await state.get_data()
    detailed_questions = data.get("detailed_questions", [])
    detailed_answers = data.get("detailed_answers", {})
    current_index = data.get("current_question_index", 0)
    
    # Сохраняем ответ на текущий вопрос
    if current_index < len(detailed_questions):
        current_question = detailed_questions[current_index]
        
        # Определяем ключ для ответа
        if isinstance(current_question, dict):
            sphere = current_question.get("sphere", "")
            question_num = sum(1 for i in range(current_index) 
                             if isinstance(detailed_questions[i], dict) 
                             and detailed_questions[i].get("sphere") == sphere) + 1
            answer_key = f"{sphere}_question_{question_num}"
        else:
            # Для обратной совместимости со старым форматом
            answer_key = f"question_{current_index + 1}"
        
        detailed_answers[answer_key] = message.text
        await state.update_data(detailed_answers=detailed_answers)
    
    # Переходим к следующему вопросу
    next_index = current_index + 1
    
    if next_index < len(detailed_questions):
        await state.update_data(current_question_index=next_index)
        
        # Сохраняем состояние в БД
        async for session in get_db():
            try:
                state_data = await state.get_data()
                await save_survey_state(
                    session,
                    message.from_user.id,
                    str(SurveyStates.detailed_questions),
                    state_data
                )
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
            break
        
        # Получаем следующий вопрос
        next_question = detailed_questions[next_index]
        if isinstance(next_question, dict):
            question_text = next_question.get("question", "")
        else:
            # Для обратной совместимости со старым форматом
            question_text = next_question
        
        # Отправляем следующий вопрос отдельным сообщением (без нумерации)
        await message.answer(question_text)
    else:
        # Все вопросы отвечены, переходим к выбору ролевой модели
        # Сохраняем состояние в БД
        async for session in get_db():
            try:
                state_data = await state.get_data()
                await save_survey_state(
                    session,
                    message.from_user.id,
                    str(SurveyStates.role_model),
                    state_data
                )
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
            break
        
        await state.set_state(SurveyStates.role_model)
        await message.answer(
            "Отлично! Теперь выбери свою ролевую модель:",
            reply_markup=get_role_model_keyboard()
        )


@router.callback_query(F.data.startswith("role_"), SurveyStates.role_model)
async def process_role_model(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора ролевой модели."""
    role_map = {
        "role_andrew_tate": "Эндрю Тейт",
        "role_grebenyuk": "Михаил Гребенюк",
        "role_khabib": "Хабиб",
        "role_oleg_tinkov": "Олег Тиньков",
        "role_tyler_durden": "Тайлер Дёрден"
    }
    
    role_model = role_map.get(callback.data, "Эндрю Тейт")
    await state.update_data(role_model=role_model)
    
    # Сохраняем состояние в БД
    async for session in get_db():
        try:
            state_data = await state.get_data()
            await save_survey_state(
                session,
                callback.from_user.id,
                str(SurveyStates.goal_3months),
                state_data
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
        break
    
    await state.set_state(SurveyStates.goal_3months)
    await callback.message.edit_text(
        "Отлично! Теперь напиши свою цель на ближайшие 3 месяца:\n"
        "(Опиши конкретно, что ты хочешь достичь)"
    )
    await callback.answer()


@router.message(SurveyStates.goal_3months)
async def process_goal_3months(message: Message, state: FSMContext):
    """Обработка цели на 3 месяца и генерация роадмапа."""
    if not message.text:
        await message.answer("Пожалуйста, отправь текст цели, а не другое сообщение")
        return
    
    goal_3months = message.text.strip()
    
    if len(goal_3months) < 10:
        await message.answer("Пожалуйста, опиши цель более подробно (минимум 10 символов)")
        return
    
    await state.update_data(goal_3months=goal_3months)
    
    # Сохраняем состояние в БД перед генерацией роадмапа
    async for session in get_db():
        try:
            state_data = await state.get_data()
            await save_survey_state(
                session,
                message.from_user.id,
                str(SurveyStates.goal_3months),
                state_data
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}", exc_info=True)
        break
    
    # Генерируем роадмап (без проверки премиума - оплата будет запрошена после первого ДЗ)
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Начинаем генерацию роадмапа для пользователя {message.from_user.id}")
    await message.answer("🗺️ Генерирую твой персональный роадмап достижения цели...")
    
    data = await state.get_data()
    basic_answers = {
        "gender": data.get("gender"),
        "age": data.get("age"),
        "name": data.get("name"),
        "values": data.get("values", []),
        "development_spheres": data.get("development_spheres", [])
    }
    detailed_answers = data.get("detailed_answers", {})
    role_model = data.get("role_model", "Эндрю Тейт")
    
    try:
        roadmap = await generate_roadmap(
            goal_3months=goal_3months,
            basic_answers=basic_answers,
            detailed_answers=detailed_answers,
            role_model=role_model
        )
        
        await state.update_data(roadmap=roadmap)
        
        # Форматируем и показываем роадмап (новый формат с этапами)
        roadmap_text = f"🗺️ РОАДМАП: {goal_3months} за 3 месяца\n\n"
        
        # Показываем новый формат, если он есть
        if roadmap.get('stage_1'):
            for stage_num in [1, 2, 3, 4]:
                stage_key = f'stage_{stage_num}'
                stage = roadmap.get(stage_key, {})
                if stage.get('goal'):
                    weeks = stage.get('weeks', f'{stage_num*3-2}-{stage_num*3}')
                    roadmap_text += f"📅 ЭТАП {stage_num} (Недели {weeks})\n"
                    roadmap_text += f"   🎯 Milestone: {stage.get('goal', '')}\n"
                    
                    result = stage.get('result', '')
                    if result:
                        roadmap_text += f"   ✅ Результат: {result}\n"
                    roadmap_text += "\n"
        else:
            # Fallback на старый формат для обратной совместимости
            roadmap_text += "📅 Первая-вторая неделя: "
            roadmap_text += f"{roadmap.get('weeks_1_2', {}).get('text', 'Цель будет определена позже')}\n\n"
            
            roadmap_text += "📅 Третья-четвертая неделя: "
            roadmap_text += f"{roadmap.get('weeks_3_4', {}).get('text', 'Цель будет определена позже')}\n\n"
            
            roadmap_text += "📅 Пятая-восьмая неделя: "
            roadmap_text += f"{roadmap.get('weeks_5_8', {}).get('text', 'Цель будет определена позже')}\n\n"
            
            roadmap_text += "📅 Девятая-двенадцатая неделя: "
            roadmap_text += f"{roadmap.get('weeks_9_12', {}).get('text', 'Цель будет определена позже')}\n\n"
        
        # Добавляем финальный результат и первый шаг
        if roadmap.get('final_result'):
            roadmap_text += f"🎯 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ: {roadmap.get('final_result')}\n\n"
        
        if roadmap.get('first_step'):
            roadmap_text += f"🚀 ПЕРВЫЙ ШАГ СЕГОДНЯ: {roadmap.get('first_step')}"
        
        await message.answer(roadmap_text)
        
        # Сохраняем все данные в БД (отдельная обработка ошибок)
        await state.set_state(SurveyStates.roadmap_generation)
        
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            async for session in get_db():
                try:
                    # Сохраняем опрос
                    survey = Survey(
                        user_id=message.from_user.id,
                        basic_answers=basic_answers,
                        detailed_answers=detailed_answers,
                        detailed_questions=data.get("detailed_questions", []),
                        role_model=role_model,
                        goal_3months=goal_3months,
                        roadmap=roadmap
                    )
                    session.add(survey)
            
                    # Обновляем пользователя (объединяем все обновления в один запрос)
                    personality_key = _map_role_model_to_personality(role_model)
                    from sqlalchemy import update
                    await session.execute(
                        update(User)
                        .where(User.user_id == message.from_user.id)
                        .values(
                            personality=personality_key,
                            name=data.get("name"),
                            gender=data.get("gender"),
                            age=data.get("age"),
                            values=data.get("values", []),
                            development_spheres=data.get("development_spheres", []),
                            goal_3months=goal_3months,
                            roadmap=roadmap
                        )
                    )
                    
                    await session.commit()
                    logger.info(f"Данные успешно сохранены в БД для пользователя {message.from_user.id}")
                    break
                except Exception as inner_db_error:
                    # Откатываем транзакцию при ошибке
                    await session.rollback()
                    logger.error(f"Внутренняя ошибка БД при сохранении: {inner_db_error}", exc_info=True)
                    raise inner_db_error
        except Exception as db_error:
            # Логируем ошибку БД, но продолжаем работу (роадмап уже отправлен)
            logger.error(f"Ошибка при сохранении данных в БД: {db_error}", exc_info=True)
            # Не прерываем процесс, так как роадмап уже успешно отправлен пользователю
        
        # Генерируем первое ДЗ (отдельная обработка ошибок)
        try:
            await message.answer("📝 Генерирую твое первое персональное задание...")
            
            first_homework = await generate_first_homework(
                basic_answers=basic_answers,
                detailed_answers=detailed_answers,
                goal_3months=goal_3months,
                roadmap=roadmap,
                role_model=role_model
            )
            
            # Сохраняем первое ДЗ в БД (отдельная обработка ошибок)
            homework_saved = False
            try:
                async for session in get_db():
                    try:
                        # Сохраняем ДЗ
                        user = await update_user_homework(session, message.from_user.id, first_homework)
                        if user and user.current_homework:
                            homework_saved = True
                            logger.info(f"ДЗ успешно сохранено для пользователя {message.from_user.id}")
                        else:
                            logger.error(f"ДЗ не было сохранено для пользователя {message.from_user.id}")
                        
                        # Устанавливаем уровень 0
                        from app.services.user_service import update_user_level
                        await update_user_level(session, message.from_user.id, 0)
                        break
                    except Exception as save_error:
                        logger.error(f"Ошибка при сохранении ДЗ в БД: {save_error}", exc_info=True)
                        await session.rollback()
                        break
            except Exception as db_error:
                logger.error(f"Ошибка при подключении к БД для сохранения ДЗ: {db_error}", exc_info=True)
            
            # Отправляем ДЗ только если оно успешно сохранено
            if homework_saved:
                # Очищаем сохраненное состояние опроса, так как опрос завершен
                async for session in get_db():
                    try:
                        await clear_survey_state(session, message.from_user.id)
                        break
                    except Exception as e:
                        logger.error(f"Ошибка очистки состояния: {e}", exc_info=True)
                        break
                
                await state.set_state(SurveyStates.finish)
                await state.clear()  # Очищаем FSM состояние
                await message.answer(
                    f"📝 Твое первое персональное задание (уровень 0):\n\n{first_homework}\n\n"
                    "Выполни задание и отправь отчет текстом. Я оценю твою работу и дам обратную связь! 💪",
                    reply_markup=get_main_keyboard()
                )
            else:
                logger.error(f"Не удалось сохранить ДЗ для пользователя {message.from_user.id}, не отправляем ДЗ")
                await state.set_state(SurveyStates.finish)
                await message.answer(
                    "Произошла ошибка при сохранении задания. Попробуй написать /start еще раз.",
                    reply_markup=get_main_keyboard()
                )
        except Exception as hw_error:
            logger.error(f"Ошибка при генерации первого ДЗ: {hw_error}", exc_info=True)
            await state.set_state(SurveyStates.finish)
            await message.answer(
                "Произошла ошибка при генерации задания. Попробуй написать /start еще раз.",
                reply_markup=get_main_keyboard()
            )
        
    except Exception as e:
        # Только ошибки генерации роадмапа попадают сюда
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при генерации роадмапа: {e}", exc_info=True)
        await message.answer(
            "Произошла ошибка при генерации роадмапа. Попробуй позже или напиши /start"
        )

