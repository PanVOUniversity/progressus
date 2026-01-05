"""Handler для команды /report.

Модуль обрабатывает отправку отчетов пользователями о выполнении
домашних заданий. Оценивает отчеты через GPT и обновляет уровень пользователя.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, Report
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
    # Проверяем, не находимся ли мы в состоянии консультации
    from app.states import SurveyStates
    current_state = await state.get_state()
    if current_state == SurveyStates.consultation:
        # Сообщение будет обработано обработчиком консультации
        return
    
    user_id = message.from_user.id
    report_text = message.text
    
    # Получаем пользователя
    async for session in get_db():
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer("Сначала пройди опрос через /start")
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
                await message.answer("Для отправки отчетов нужен Premium доступ. Активируй его через /start")
                break
        
        if not user.current_homework:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Пользователь {user_id} пытается отправить отчет, но у него нет активного ДЗ")
            await message.answer("У тебя нет активного ДЗ. Пройди опрос через /start")
            break
        
        # Оцениваем отчет через GPT
        await message.answer("Оцениваю твой отчет...")
        
        try:
            level_before = user.level
            personality_key = user.personality or "andrew_tate"
            feedback, new_level, homework_or_revision, needs_revision = await evaluate_report_with_revision(
                user.level,
                user.category or "finances",
                report_text,
                user.current_homework,
                personality_key
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
                    level_up_text = f"\n\n🎉 Твой уровень повышен с {level_before} до {new_level}!"
                
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
                    f"✅ Красавчик! Ты проделал отличную работу!\n\n"
                    f"{clean_markdown(clean_feedback)}{level_up_text}\n\n"
                    f"Новый уровень: {new_level}\nНовое домашнее задание:\n{clean_markdown(clean_homework)}"
                )
                
                # Если это был первый отчет, запрашиваем оплату после проверки
                if is_first_report:
                    from app.keyboards import get_payment_keyboard
                    from app.config import settings
                    price_rub = settings.PREMIUM_PRICE // 100
                    await message.answer(
                        f"💎 Для продолжения работы нужен Premium доступ\n\n"
                        f"Premium включает:\n"
                        f"✅ Персональный роадмап достижения цели\n"
                        f"✅ Ежедневные задания от ИИ-коуча\n"
                        f"✅ Обратная связь по отчетам\n"
                        f"✅ Трекинг прогресса\n\n"
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
                    f"📝 Правки к ДЗ:\n{clean_markdown(clean_homework)}\n\n"
                    f"Переделай задание с учетом этих правок и отправь новый отчет."
                )
                
                # Если это был первый отчет, запрашиваем оплату после проверки
                if is_first_report:
                    from app.keyboards import get_payment_keyboard
                    from app.config import settings
                    price_rub = settings.PREMIUM_PRICE // 100
                    await message.answer(
                        f"💎 Для продолжения работы нужен Premium доступ\n\n"
                        f"Premium включает:\n"
                        f"✅ Персональный роадмап достижения цели\n"
                        f"✅ Ежедневные задания от ИИ-коуча\n"
                        f"✅ Обратная связь по отчетам\n"
                        f"✅ Трекинг прогресса\n\n"
                        f"Стоимость: {price_rub} руб./месяц",
                        reply_markup=get_payment_keyboard()
                    )
            
            await session.commit()
            
        except Exception as e:
            await message.answer(
                "Произошла ошибка при оценке отчета. Попробуй позже."
            )
        
        break

