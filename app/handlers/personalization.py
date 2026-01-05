"""Handler для персонализации пользователя.

Модуль обрабатывает глубокие вопросы для лучшего понимания пользователя
и сохранения контекста в БД.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.keyboards import get_main_keyboard, get_main_menu_keyboard
from app.database import get_db
from app.models import User
from app.states import SurveyStates
from app.gpt import client, clean_markdown
from app.config import settings
from typing import Dict, List
import logging
import re

logger = logging.getLogger(__name__)

router = Router()
"""Роутер для обработки персонализации."""


async def generate_personalization_response(user: User, user_message: str) -> tuple[str, List[str], int]:
    """Генерирует ответ коуча с отражением и вопросами для персонализации.
    
    На основе последнего сообщения пользователя генерирует отражение его ответа
    и 1-3 уточняющих вопроса (если счетчик < 20).
    
    Args:
        user (User): Объект пользователя из БД
        user_message (str): Последнее сообщение пользователя
        
    Returns:
        tuple[str, List[str], int]: Кортеж из (отражение, список вопросов, новый счетчик)
    """
    # Получаем текущий счетчик вопросов
    personalization_data = user.personalization_data or {}
    question_count = personalization_data.get("question_count", 0)
    existing_answers = personalization_data.get("answers", {})
    
    # Если достигли лимита, возвращаем только рекомендации
    if question_count >= 20:
        return (
            f"Отлично! Собрал 20/20 вопросов — теперь у меня полная картина твоей личности, болей, стиля и ресурсов.\n\n"
            f"Теперь переходим только к точным заданиям, рекомендациям и движению к твоей цели {user.goal_3months or 'развития'}. "
            f"Без лишних вопросов — только результат!",
            [],
            20
        )
    
    # Формируем контекст о пользователе
    user_context = f"""Информация о пользователе:
- Пол: {user.gender or 'не указано'}
- Возраст: {user.age or 'не указано'}
- Имя: {user.name or 'не указано'}
- Три основных ценности: {', '.join(user.values or [])}
- Сферы развития: {', '.join(user.development_spheres or [])}
- Ролевая модель: {user.personality or 'не указана'}
- Цель на 3 месяца: {user.goal_3months or 'не указана'}
- Уровень: {user.level}
- Категория: {user.category or 'не указана'}
"""
    
    # Добавляем последние ответы для контекста
    if existing_answers:
        user_context += f"\nПоследние ответы пользователя:\n"
        for q, a in list(existing_answers.items())[-3:]:  # Последние 3 ответа
            user_context += f"- {q}: {a}\n"
    
    # Формируем промпт
    prompt = f"""{user_context}

ТЕКУЩИЙ СЧЕТЧИК ВОПРОСОВ: {question_count}/20

Пользователь написал: "{user_message}"

Твоя задача:
1. Коротко отрази и структурируй его ответ (1-3 предложения)
2. Затем задай 1-3 уточняющих вопроса (только если счетчик < 20)

ПРАВИЛА:
- Вопросы должны быть конкретными (без «расскажи о себе»)
- Вопросы должны быть открытыми (чтобы ответ нельзя было дать «да/нет»)
- Вопросы должны быть привязанными к его словам (используй его формулировки)
- Вопросы должны быть безопасными, но честными — можно мягко «жечь», но без токсичности
- Максимум 3 вопроса за один ответ
- Каждый вопрос считается отдельно (3 вопроса = +3 к счетчику)

Категории вопросов (выбери 1-3):
1) ЦЕЛЬ И КОНТЕКСТ - как понять что достиг цели, почему именно это число/состояние, что изменится
2) БОЛИ И ПРЕПЯТСТВИЯ - что мешает, где застревает, чего боится
3) ПРОШЛЫЙ ОПЫТ - что пробовал раньше, что получилось, что не получилось
4) ЦЕННОСТИ И МОТИВАЦИЯ - почему важно, что главное, кого уважает
5) СТИЛЬ ДЕЙСТВИЯ И ХАРАКТЕР - как действует, системно или рывками, ежедневно или периодами
6) РЕСУРСЫ И ОКРУЖЕНИЕ - что уже есть, кто в окружении, на что тратит время

ФОРМАТ ОТВЕТА:
Если счетчик < 20:
Краткое отражение:
"Смотри, по сути ты сейчас в такой точке: [резюме его сообщения]."

Мини-структура:
"Я вижу здесь несколько ключевых моментов: [1], [2], [3]."

Вопросы (Вопросы: X/20):

Вопрос 1

Вопрос 2

Вопрос 3 (если нужно)

ВАЖНО: 
- Не используй звездочки или markdown форматирование
- Показывай счетчик в формате "Вопросы: X/20" после каждого вопроса
- Если счетчик достигнет 20, напиши финальное сообщение о завершении сбора данных

ВАЖНО: Не форматируй текст *. Пиши обычным текстом без звездочек и форматирования."""

    try:
        system_prompt = """[СИСТЕМНОЕ ОПРЕДЕЛЕНИЕ]
Ты — персональный AI-коуч, который в процессе диалога постепенно раскрывает пользователя и улучшает его персональную модель. Твоя задача — при каждом значимом сообщении пользователя задавать 1–3 уточняющих вопроса, которые помогают лучше понять:

- его цели и подцели,
- боли и реальные ограничения,
- стиль мышления и действия,
- мотивацию и ценности,
- страхи, саботаж и внутренние конфликты.

Вопросы всегда строятся на основе последних ответов пользователя, а не задаются случайно.

КРИТИЧНОЕ ОГРАНИЧЕНИЕ: МАКСИМУМ 20 ВОПРОСОВ ВСЕГО
- Веди счет заданных вопросов (счетчик сбрасывается только при новом пользователе)
- Когда достигнешь 20 вопросов — ПЕРЕСТАЙ задавать новые вопросы
- После 20 вопросов переходи только к анализу, рекомендациям, заданиям без вопросов
- Показывай пользователю счетчик: "Вопросы: X/20" в каждом сообщении с вопросами"""

        response = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=800
        )
        
        response_text = response.choices[0].message.content
        response_text = clean_markdown(response_text)
        
        # Парсим ответ: отделяем отражение и вопросы
        lines = response_text.split('\n')
        reflection_parts = []
        questions = []
        in_questions_section = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Определяем начало секции вопросов
            if 'вопрос' in line.lower() and ('вопросы:' in line.lower() or 'вопросы ' in line.lower()):
                in_questions_section = True
                # Извлекаем счетчик из строки
                count_match = re.search(r'(\d+)/20', line)
                if count_match:
                    question_count = int(count_match.group(1))
                continue
            
            if in_questions_section:
                # Это вопрос
                # Убираем нумерацию
                question = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                if question and len(question) > 10:
                    questions.append(question)
            else:
                # Это часть отражения
                if line and not line.lower().startswith(('вопрос', 'вопросы')):
                    reflection_parts.append(line)
        
        # Если не удалось распарсить, пробуем другой подход
        if not questions and not reflection_parts:
            # Делим на части по пустым строкам
            parts = [p.strip() for p in response_text.split('\n\n') if p.strip()]
            if parts:
                reflection_parts = [parts[0]]
                if len(parts) > 1:
                    # Остальное - вопросы
                    for part in parts[1:]:
                        # Ищем вопросы в части
                        for line in part.split('\n'):
                            line = line.strip()
                            if line and len(line) > 10 and '?' in line:
                                question = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                                if question:
                                    questions.append(question)
        
        # Формируем отражение
        reflection = '\n\n'.join(reflection_parts) if reflection_parts else "Понял тебя."
        
        # Подсчитываем новые вопросы
        new_question_count = min(question_count + len(questions), 20)
        
        return reflection, questions[:3], new_question_count  # Максимум 3 вопроса
        
    except Exception as e:
        logger.error(f"Ошибка генерации ответа персонализации: {e}", exc_info=True)
        # Возвращаем базовое отражение без вопросов при ошибке
        return "Понял тебя. Продолжай.", [], question_count


@router.callback_query(F.data == "menu_personalization")
async def cmd_personalization(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки "Персонализация" в меню.
    
    Начинает процесс персонализации - генерирует и задает глубокие вопросы.
    
    Args:
        callback (CallbackQuery): Callback от inline кнопки
        state (FSMContext): Контекст FSM
    """
    user_id = callback.from_user.id
    message = callback.message
    
    await callback.answer()
    
    # Получаем пользователя
    async for session in get_db():
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Сначала пройди опрос через /start")
            break
        
        # Проверяем доступность персонализации (после первого использования без премиума)
        from app.services.user_service import is_premium_active
        premium_active = await is_premium_active(session, user_id)
        
        # Проверяем, использована ли персонализация (если есть хотя бы один ответ)
        personalization_data = user.personalization_data or {}
        answers = personalization_data.get("answers", {})
        personalization_used = len(answers) > 0
        
        if not premium_active and personalization_used:
            await message.answer(
                "❌ Ты уже использовал бесплатную персонализацию.\n\n"
                "Для неограниченной персонализации активируй Premium доступ через меню 'Оплата'.",
                reply_markup=get_main_keyboard()
            )
            break
        
        # Переходим в состояние персонализации
        await state.set_state(SurveyStates.personalization)
        
        # Проверяем счетчик вопросов
        question_count = personalization_data.get("question_count", 0)
        
        if question_count >= 20:
            await message.answer(
                "✅ Отлично! Собрал 20/20 вопросов — теперь у меня полная картина твоей личности, болей, стиля и ресурсов.\n\n"
                "Теперь переходим только к точным заданиям, рекомендациям и движению к твоей цели. "
                "Без лишних вопросов — только результат!\n\n"
                "Напиши, что тебя интересует, и я дам конкретные рекомендации.",
                reply_markup=get_main_keyboard()
            )
            break
        
        # Приветственное сообщение
        await message.answer(
            "🔍 Давай лучше узнаем друг друга!\n\n"
            f"Я задам тебе несколько уточняющих вопросов (сейчас задано: {question_count}/20). "
            "Отвечай честно — это поможет мне давать более точные рекомендации.\n\n"
            "Напиши что-нибудь о себе, своих целях или проблемах, и я задам уточняющие вопросы.",
            reply_markup=get_main_keyboard()
        )
        
        break


@router.message(SurveyStates.personalization)
async def process_personalization_answer(message: Message, state: FSMContext):
    """Обработка ответов на вопросы персонализации.
    
    Генерирует отражение ответа и новые вопросы на основе сообщения пользователя.
    Сохраняет ответы и обновляет счетчик вопросов.
    
    Args:
        message (Message): Сообщение с ответом пользователя
        state (FSMContext): Контекст FSM
    """
    user_id = message.from_user.id
    user_answer = message.text
    
    # Проверяем, не является ли это командой выхода
    if user_answer in ["Меню", "/menu", "menu", "Свободная консультация", "Задания", "Оплата", "Реферальная программа", "🔄 Рестарт", "/restart"]:
        # Сохраняем данные в БД перед выходом
        await save_personalization_data(user_id, state)
        await state.clear()
        
        # Показываем меню
        from app.handlers.menu import show_main_menu
        await show_main_menu(message, state)
        return
    
    # Получаем пользователя
    async for session in get_db():
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Сначала пройди опрос через /start")
            await state.clear()
            break
        
        # Проверяем доступность персонализации (после первого использования без премиума)
        from app.services.user_service import is_premium_active
        premium_active = await is_premium_active(session, user_id)
        
        # Проверяем, использована ли персонализация (если есть хотя бы один ответ)
        personalization_data = user.personalization_data or {}
        answers = personalization_data.get("answers", {})
        personalization_used = len(answers) > 0
        
        if not premium_active and personalization_used:
            await message.answer(
                "❌ Ты уже использовал бесплатную персонализацию.\n\n"
                "Для неограниченной персонализации активируй Premium доступ через меню 'Оплата'.",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            break
        
        # Генерируем ответ с отражением и вопросами
        await message.answer("🤔 Анализирую твой ответ...")
        
        try:
            reflection, questions, new_question_count = await generate_personalization_response(user, user_answer)
            
            # Получаем текущие данные из состояния
            data = await state.get_data()
            answers = data.get("personalization_answers", {})
            
            # Сохраняем ответ пользователя
            # Если был предыдущий вопрос, сохраняем ответ на него
            last_question = data.get("last_question", "")
            if last_question:
                answers[last_question] = user_answer
            else:
                # Если это первое сообщение, сохраняем как общий ответ
                answers[f"Сообщение_{len(answers) + 1}"] = user_answer
            
            # Формируем ответное сообщение
            response_text = reflection
            
            if questions and new_question_count < 20:
                response_text += "\n\n"
                # Получаем текущий счетчик из БД для правильного отображения
                # Используем счетчик ДО добавления новых вопросов
                personalization_data = user.personalization_data or {}
                current_question_count = personalization_data.get("question_count", 0)
                
                # Нумеруем вопросы начиная с current_question_count + 1
                for i, question in enumerate(questions, 1):
                    question_number = current_question_count + i
                    if question_number <= 20:
                        response_text += f"\nВопрос {question_number}/20\n{question}"
            
            # Отправляем ответ
            await message.answer(
                response_text,
                reply_markup=get_main_keyboard()
            )
            
            # Обновляем состояние
            # Сохраняем первый вопрос как последний заданный (для следующего ответа)
            last_question_to_save = questions[0] if questions else ""
            await state.update_data(
                personalization_answers=answers,
                last_question=last_question_to_save,
                question_count=new_question_count
            )
            
            # Сохраняем в БД
            await save_personalization_data(user_id, state, new_question_count)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке ответа персонализации: {e}", exc_info=True)
            await message.answer(
                "❌ Произошла ошибка при обработке ответа. Попробуй еще раз.",
                reply_markup=get_main_keyboard()
            )
        
        break


async def save_personalization_data(user_id: int, state: FSMContext, question_count: int = None):
    """Сохраняет данные персонализации в БД.
    
    Args:
        user_id (int): ID пользователя
        state (FSMContext): Контекст FSM с данными персонализации
        question_count (int, optional): Текущий счетчик вопросов
    """
    try:
        data = await state.get_data()
        answers = data.get("personalization_answers", {})
        
        if not answers and question_count is None:
            return  # Нет данных для сохранения
        
        async for session in get_db():
            # Получаем текущие данные персонализации
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                break
            
            # Объединяем с существующими данными
            existing_data = user.personalization_data or {}
            existing_answers = existing_data.get("answers", {})
            existing_question_count = existing_data.get("question_count", 0)
            
            # Объединяем ответы
            all_answers = dict(existing_answers)
            all_answers.update(answers)
            
            # Обновляем счетчик вопросов
            if question_count is not None:
                new_question_count = question_count
            else:
                # Если счетчик не передан, берем из state
                state_question_count = data.get("question_count")
                if state_question_count is not None:
                    new_question_count = state_question_count
                else:
                    new_question_count = existing_question_count
            
            # Сохраняем в БД
            personalization_data = {
                "answers": all_answers,
                "question_count": new_question_count,
                "last_updated": None  # Можно добавить timestamp
            }
            
            await session.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(personalization_data=personalization_data)
            )
            await session.commit()
            
            logger.info(f"Данные персонализации сохранены для пользователя {user_id}, вопросов: {new_question_count}/20")
            break
            
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных персонализации: {e}", exc_info=True)

