"""Конфигурация приложения - все токены и настройки.

Модуль загружает переменные окружения из файла .env и предоставляет
класс Settings для доступа к настройкам приложения.

Attributes:
    settings: Глобальный экземпляр настроек приложения
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()


class Settings:
    """Настройки приложения из переменных окружения.
    
    Класс содержит все необходимые настройки для работы бота:
    токены, URL базы данных, Redis, настройки платежей и т.д.
    Все значения загружаются из переменных окружения.
    
    Attributes:
        BOT_TOKEN (str): Токен Telegram бота от BotFather
        BOT_USERNAME (Optional[str]): Username бота (без @)
        OPENROUTER_API_KEY (str): API ключ для OpenRouter
        OPENROUTER_MODEL (str): Модель GPT для использования (по умолчанию openai/gpt-4o-mini)
        DB_URL (str): URL подключения к PostgreSQL базе данных
        REDIS_URL (str): URL подключения к Redis
        PROVIDER_TOKEN (str): Токен провайдера платежей от BotFather
        PRIVACY_POLICY_URL (str): URL политики конфиденциальности
        WEBHOOK_URL (Optional[str]): URL для webhook (если None, используется polling)
        WEBHOOK_SECRET (Optional[str]): Секретный токен для webhook
        ENVIRONMENT (str): Окружение (development/production)
    """
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    """Токен Telegram бота от BotFather."""
    
    BOT_USERNAME: Optional[str] = os.getenv("BOT_USERNAME")
    """Username бота без символа @."""
    
    # OpenRouter API (замена OpenAI)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    """API ключ для доступа к OpenRouter."""
    
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    """Модель GPT для использования через OpenRouter."""
    
    # Database
    DB_URL: str = os.getenv("DB_URL", "postgresql+asyncpg://user:password@localhost:5432/progressusbot")
    """URL подключения к PostgreSQL базе данных."""
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    """URL подключения к Redis для FSM storage и Celery broker."""
    
    # Payments
    PROVIDER_TOKEN: str = os.getenv("PROVIDER_TOKEN", "")
    """Токен провайдера платежей от BotFather."""
    
    PREMIUM_PRICE: int = int(os.getenv("PREMIUM_PRICE", "29900"))  # В копейках
    """Цена premium доступа в копейках (по умолчанию 299 руб = 29900 копеек)."""
    
    # Referral System
    REFERRALS_FOR_PREMIUM: int = int(os.getenv("REFERRALS_FOR_PREMIUM", "3"))
    """Количество рефералов, необходимое для получения месяца бесплатного премиума."""
    
    REFERRALS_TO_REGISTER: int = int(os.getenv("REFERRALS_TO_REGISTER", "1"))
    """Количество рефералов, которые должны зарегистрироваться (для статистики)."""
    
    # Privacy Policy
    PRIVACY_POLICY_URL: str = os.getenv("PRIVACY_POLICY_URL", "https://example.com/privacy")
    """URL политики конфиденциальности."""
    
    # Webhook
    WEBHOOK_URL: Optional[str] = os.getenv("WEBHOOK_URL")
    """URL для webhook (если None, используется polling режим)."""
    
    WEBHOOK_SECRET: Optional[str] = os.getenv("WEBHOOK_SECRET")
    """Секретный токен для проверки webhook запросов."""
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    """Окружение приложения: development или production."""
    
    # Yandex SpeechKit
    YANDEX_SPEECHKIT_API_KEY: str = os.getenv("YANDEX_SPEECHKIT_API_KEY", "")
    """API ключ для Yandex SpeechKit (идентификатор ключа)."""
    


# Глобальный экземпляр настроек
settings = Settings()
"""Глобальный экземпляр настроек приложения."""

