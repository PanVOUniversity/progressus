"""Celery задачи для отправки уведомлений.

Модуль содержит фоновые задачи Celery для отправки ежедневных
домашних заданий и напоминаний пользователям.
"""
from celery_app.celery_worker import celery_app
from aiogram import Bot
from sqlalchemy import select
from app.config import settings
# OpenRouter уже настроен в app.gpt, импорт не нужен
from app.models import User
from app.database import async_session_maker
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
"""Логгер для модуля tasks."""


@celery_app.task
async def send_daily_homework(user_id: int):
    """Отправляет ежедневное домашнее задание пользователю.
    
    Получает пользователя из БД, проверяет наличие premium доступа
    и активного ДЗ, затем отправляет ДЗ пользователю через бота.
    
    Args:
        user_id (int): Telegram ID пользователя
        
    Note:
        Задача выполняется только для пользователей с premium доступом.
        Если у пользователя нет активного ДЗ, отправляется сообщение об этом.
    """
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        
        async with async_session_maker() as session:
            from app.services.user_service import is_premium_active
            if not await is_premium_active(session, user_id):
                return
            
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                return
            
            if user.current_homework:
                await bot.send_message(
                    user_id,
                    f"📋 Твое ДЗ на сегодня:\n\n{user.current_homework}"
                )
            else:
                await bot.send_message(
                    user_id,
                    "У тебя пока нет активного ДЗ. Пройди опрос через /start"
                )
        
        await bot.session.close()
    except Exception as e:
        logger.error(f"Error sending daily homework to {user_id}: {e}")


@celery_app.task
async def send_reminder(user_id: int):
    """Отправляет напоминание об отчете если не было отчета за 2 дня.
    
    Проверяет дату последнего отчета пользователя. Если прошло 2 или более дней
    с последнего отчета (или отчетов не было), отправляет напоминание.
    
    Args:
        user_id (int): Telegram ID пользователя
        
    Note:
        Задача выполняется только для пользователей с premium доступом.
        Если пользователь никогда не отправлял отчет, отправляется сообщение
        о необходимости отправить первый отчет.
    """
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        
        async with async_session_maker() as session:
            from app.services.user_service import is_premium_active
            if not await is_premium_active(session, user_id):
                return
            
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                return
            
            # Проверяем последний отчет
            if user.last_report:
                days_since_report = (datetime.utcnow().date() - user.last_report).days
                if days_since_report >= 2:
                    await bot.send_message(
                        user_id,
                        "⏰ Напоминание: ты не отправлял отчет уже 2 дня. "
                        "Отправь отчет через /report чтобы продолжить прогресс!"
                    )
            else:
                # Если никогда не отправлял отчет
                await bot.send_message(
                    user_id,
                    "⏰ Напоминание: отправь свой первый отчет через /report!"
                )
        
        await bot.session.close()
    except Exception as e:
        logger.error(f"Error sending reminder to {user_id}: {e}")


@celery_app.task
def schedule_daily_tasks():
    """Планирует ежедневные задачи для всех premium пользователей.
    
    Эта задача должна запускаться по расписанию (например, в 9:00 МСК)
    и вызывать send_daily_homework для всех premium пользователей.
    
    Note:
        В текущей версии функция не реализована (pass). Нужно добавить логику
        получения списка всех premium пользователей и вызова send_daily_homework
        для каждого из них.
    """
    # Эта задача должна запускаться по расписанию (например, в 9:00 МСК)
    # и вызывать send_daily_homework для всех premium пользователей
    pass

