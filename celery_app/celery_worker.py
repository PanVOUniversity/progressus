"""Celery app configuration.

Модуль настраивает и создает экземпляр Celery приложения для выполнения
фоновых задач (отправка уведомлений, напоминаний и т.д.).
"""
from celery import Celery
from app.config import settings

# Создаем Celery app
celery_app = Celery(
    "progressusbot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["celery_app.tasks"]
)
"""Экземпляр Celery приложения для фоновых задач."""

# Конфигурация
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут
    task_soft_time_limit=25 * 60,  # 25 минут
)
"""Конфигурация Celery приложения.

Настройки:
    - Сериализация: JSON
    - Часовой пояс: Europe/Moscow
    - Лимит выполнения задачи: 30 минут (мягкий лимит: 25 минут)
"""

