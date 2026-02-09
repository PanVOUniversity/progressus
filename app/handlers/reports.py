"""Handler для команды /report.

Модуль обрабатывает отправку отчетов пользователями о выполнении
домашних заданий. Оценивает отчеты через GPT и обновляет уровень пользователя.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, Report, Survey
from app.gpt import evaluate_report_with_revision, clean_markdown
from app.services.user_service import update_user_level, update_user_homework
from app.database import get_db

router = Router()
"""Роутер для обработки отчетов."""


@router.message(F.text == "/report")
async def cmd_report(message: Message):
    """Обработка команды /report - запрос текста отчета.
    
    Отправляет пользователю сообщение с просьбой написать отчет
    о выполнении домашнего задания.
    
    Args:
        message (Message): Сообщение с командой /report
    """
    await message.answer(
        "Напиши отчет о выполнении ДЗ. Опиши, что ты сделал, какие результаты получил."
    )


@router.message(F.text.len() > 10, ~F.text.startswith("/"), ~F.command())
async def process_report(message: Message, state: FSMContext):
    """Обработка текста отчета пользователя.
    
    Проверяет наличие premium доступа и активного ДЗ, отправляет отчет
    в GPT для оценки, сохраняет отчет в БД, обновляет уровень пользователя
    и отправляет обратную связь с новым ДЗ.
    
    Args:
        message (Message): Текстовое сообщение с отчетом пользователя
        state (FSMContext): Контекст FSM
        
    Note:
        Обрабатывает только сообщения длиннее 10 символов, которые не являются командами.
        Требует наличия premium доступа и активного домашнего задания.
        Не обрабатывает сообщения в состоянии консультации.
    """
    # Проверяем, не находимся ли мы в состоянии опроса или консультации
    from app.states import SurveyStates
    import logging
    logger = logging.getLogger(__name__)
    current_state = await state.get_state()
    
    # Логируем текущее состояние для диагностики
    logger.info(f"Обработчик отчетов: пользователь {message.from_user.id}, состояние: {current_state}, текст: {message.text[:50] if message.text else 'None'}...")
    
    # Если пользователь находится в процессе опроса или консультации, не обрабатываем как отчет
    # Состояние finish НЕ блокирует обработку отчетов, так как опрос уже завершен
    if current_state in [
        SurveyStates.consultation,
        SurveyStates.gender,
        SurveyStates.age,
        SurveyStates.name,
        SurveyStates.values,
        SurveyStates.development_spheres,
        SurveyStates.detailed_questions,
        SurveyStates.role_model,
        SurveyStates.goal_3months,
        SurveyStates.roadmap_vision,
        SurveyStates.roadmap_generation,
        SurveyStates.roadmap_review,
        SurveyStates.roadmap_feedback,
        SurveyStates.personalization,
        SurveyStates.promo_code
    ]:
        # Сообщение будет обработано соответствующим обработчиком опроса
        logger.info(f"Сообщение не обрабатывается как отчет, так как пользователь в состоянии опроса: {current_state}")
        return
    
    user_id = message.from_user.id
    report_text = message.text
    
    # Получаем пользователя
    async for session in get_db():
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Сначала пройди опрос через /restart")
            break
        
        # Проверяем, это ли первый отчет (уровень 0 и нет отчетов в БД)
        from sqlalchemy import func
        reports_count = await session.execute(
            select(func.count(Report.id)).where(Report.user_id == user_id)
        )
        is_first_report = reports_count.scalar() == 0 and user.level == 0
        
        # Для первого отчета не требуем премиум, для остальных - требуем
        if not is_first_report:
            from app.services.user_service import is_premium_active
            if not await is_premium_active(session, user_id):
                await message.answer("Для отправки отчетов нужен Premium доступ. Активируй его через /menu")
                break
        
        if not user.current_homework:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Пользователь {user_id} пытается отправить отчет, но у него нет активного ДЗ. User level: {user.level}, goal_3months: {bool(user.goal_3months)}, roadmap: {bool(user.roadmap)}")
            await message.answer("У тебя нет активного ДЗ. Пройди опрос через /restart")
            break
        
        # Оцениваем отчет через GPT
        await message.answer("Оцениваю твой отчет...")
        
        try:
            level_before = user.level
            personality_key = user.personality or "andrew_tate"
            
            # Получаем данные пользователя для промпта
            user_goal = user.goal_3months or "достижение цели"
            
            # Определяем архетип на основе сфер развития
            user_archetype = "Результат-ориентированный"  # по умолчанию
            if user.development_spheres:
                if "Разум" in user.development_spheres or "Коммуникации" in user.development_spheres:
                    user_archetype = "Аналитичный"
                if any(v in ["Лидерство", "Власть", "Влияние"] for v in (user.values or [])):
                    user_archetype = "Лидерский"
            
            # Формируем строку ценностей
            user_values = ", ".join(user.values[:3]) if user.values and len(user.values) > 0 else "Деньги, Власть, Действие"
            
            # Получаем ролевую модель из последнего опроса или используем personality
            user_role_model = personality_key
            try:
                # Получаем последний опрос через запрос, чтобы избежать проблем с lazy loading
                last_survey_result = await session.execute(
                    select(Survey)
                    .where(Survey.user_id == user_id)
                    .order_by(Survey.created_at.desc())
                    .limit(1)
                )
                last_survey = last_survey_result.scalar_one_or_none()
                if last_survey and last_survey.role_model:
                    user_role_model = last_survey.role_model
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Не удалось получить ролевую модель из опроса: {e}, используем {personality_key}")
            
            feedback, new_level, homework_or_revision, needs_revision = await evaluate_report_with_revision(
                user.level,
                user.category or "finances",
                report_text,
                user.current_homework,
                personality_key,
                user_goal=user_goal,
                user_archetype=user_archetype,
                user_values=user_values,
                user_role_model=user_role_model
            )
            
            # Сохраняем отчет
            report = Report(
                user_id=user_id,
                report_text=report_text,
                gpt_feedback=feedback,
                level_before=level_before,
                level_after=new_level,
                is_approved=not needs_revision,
                revision_required=needs_revision
            )
            session.add(report)
            
            # Обновляем уровень и ДЗ
            if not needs_revision:
                # ДЗ выполнено хорошо - переходим к новому ДЗ
                await update_user_level(session, user_id, new_level)
                await update_user_homework(session, user_id, homework_or_revision)
                
                # Сбрасываем флаг правок
                from sqlalchemy import update
                await session.execute(
                    update(User)
                    .where(User.user_id == user_id)
                    .values(homework_needs_revision=False)
                )
                
                level_up_text = ""
                if new_level > level_before:
                    level_up_text = f"\n\nТвой уровень повышен с {level_before} до {new_level}!"
                
                # Очищаем feedback от маркеров GPT
                clean_feedback = feedback
                # Удаляем все маркеры GPT из feedback
                import re
                # Удаляем строки с маркерами
                feedback_lines = clean_feedback.split('\n')
                clean_feedback_lines = []
                for line in feedback_lines:
                    line_upper = line.upper()
                    # Пропускаем строки с маркерами GPT
                    if any(marker in line_upper for marker in ['APPROVED:', 'FEEDBACK:', 'NEW_LEVEL:', 'NEWLEVEL:', 'NEW_HOMEWORK_OR_REVISION:', 'NEWHOMEWORKORREVISION:']):
                        # Если в строке есть текст после маркера, берем только его
                        for marker in ['APPROVED:', 'FEEDBACK:', 'NEW_LEVEL:', 'NEWLEVEL:', 'NEW_HOMEWORK_OR_REVISION:', 'NEWHOMEWORKORREVISION:']:
                            if marker in line_upper:
                                parts = line.split(':', 1)
                                if len(parts) > 1 and parts[1].strip():
                                    # Оставляем только текст после маркера, если он есть
                                    continue
                        continue
                    clean_feedback_lines.append(line)
                clean_feedback = '\n'.join(clean_feedback_lines).strip()
                
                # Очищаем homework от маркеров
                clean_homework = homework_or_revision
                # Удаляем маркеры из начала текста
                markers_to_remove = ["NEWLEVEL:", "NEW_LEVEL:", "NEWHOMEWORKORREVISION:", "NEW_HOMEWORK_OR_REVISION:"]
                for marker in markers_to_remove:
                    marker_upper = marker.upper()
                    if marker_upper in clean_homework.upper():
                        # Находим позицию маркера и берем текст после него
                        marker_pos = clean_homework.upper().find(marker_upper)
                        if marker_pos != -1:
                            clean_homework = clean_homework[marker_pos + len(marker):].strip()
                            # Убираем все, что до первого значимого текста
                            while clean_homework and clean_homework[0] in [' ', ':', '\n', '\t']:
                                clean_homework = clean_homework[1:].strip()
                
                await message.answer(
                    f"Красавчик! Ты проделал отличную работу!\n\n"
                    f"{clean_markdown(clean_feedback)}{level_up_text}\n\n"
                    f"Новый уровень: {new_level}\nНовое домашнее задание:\n{clean_markdown(clean_homework)}"
                )
                
                # Если это был первый отчет, запрашиваем оплату после проверки
                if is_first_report:
                    from app.keyboards import get_payment_keyboard
                    from app.config import settings
                    price_rub = settings.PREMIUM_PRICE // 100
                    await message.answer(
                        f"Для продолжения работы нужен Premium доступ\n\n"
                        f"Premium включает:\n"
                        f"- Персональный роадмап достижения цели\n"
                        f"- Ежедневные задания от ИИ-коуча\n"
                        f"- Обратная связь по отчетам\n"
                        f"- Трекинг прогресса\n\n"
                        f"Стоимость: {price_rub} руб./месяц",
                        reply_markup=get_payment_keyboard()
                    )
            else:
                # ДЗ требует правок - оставляем то же ДЗ с правками
                await update_user_homework(session, user_id, homework_or_revision)
                
                # Устанавливаем флаг правок
                from sqlalchemy import update
                await session.execute(
                    update(User)
                    .where(User.user_id == user_id)
                    .values(homework_needs_revision=True)
                )
                
                # Очищаем feedback от маркеров GPT
                clean_feedback = feedback
                import re
                # Удаляем строки с маркерами из feedback
                feedback_lines = clean_feedback.split('\n')
                clean_feedback_lines = []
                for line in feedback_lines:
                    line_upper = line.upper()
                    # Пропускаем строки с маркерами GPT
                    if any(marker in line_upper for marker in ['APPROVED:', 'FEEDBACK:', 'NEW_LEVEL:', 'NEWLEVEL:', 'NEW_HOMEWORK_OR_REVISION:', 'NEWHOMEWORKORREVISION:']):
                        continue
                    clean_feedback_lines.append(line)
                clean_feedback = '\n'.join(clean_feedback_lines).strip()
                
                # Очищаем homework от маркеров
                clean_homework = homework_or_revision
                markers_to_remove = ["NEWLEVEL:", "NEW_LEVEL:", "NEWHOMEWORKORREVISION:", "NEW_HOMEWORK_OR_REVISION:"]
                for marker in markers_to_remove:
                    marker_upper = marker.upper()
                    if marker_upper in clean_homework.upper():
                        # Находим позицию маркера и берем текст после него
                        marker_pos = clean_homework.upper().find(marker_upper)
                        if marker_pos != -1:
                            clean_homework = clean_homework[marker_pos + len(marker):].strip()
                            # Убираем все, что до первого значимого текста
                            while clean_homework and clean_homework[0] in [' ', ':', '\n', '\t']:
                                clean_homework = clean_homework[1:].strip()
                
                await message.answer(
                    f"{clean_markdown(clean_feedback)}\n\n"
                    f"Правки к ДЗ:\n{clean_markdown(clean_homework)}\n\n"
                    f"Переделай задание с учетом этих правок и отправь новый отчет."
                )
                
                # Если это был первый отчет, запрашиваем оплату после проверки
                if is_first_report:
                    from app.keyboards import get_payment_keyboard
                    from app.config import settings
                    price_rub = settings.PREMIUM_PRICE // 100
                    await message.answer(
                        f"Для продолжения работы нужен Premium доступ\n\n"
                        f"Premium включает:\n"
                        f"- Персональный роадмап достижения цели\n"
                        f"- Ежедневные задания от ИИ-коуча\n"
                        f"- Обратная связь по отчетам\n"
                        f"- Трекинг прогресса\n\n"
                        f"Стоимость: {price_rub} руб./месяц",
                        reply_markup=get_payment_keyboard()
                    )
            
            await session.commit()
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при оценке отчета для пользователя {user_id}: {e}", exc_info=True)
            await message.answer(
                f"Произошла ошибка при оценке отчета. Попробуй позже.\n\n"
                f"Техническая информация: {str(e)[:200]}"
            )
        
        break

