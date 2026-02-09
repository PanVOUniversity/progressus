"""Rate limiting middleware (30 запросов/мин на пользователя).

Модуль содержит middleware для ограничения частоты запросов от пользователей
с целью защиты от спама и злоупотреблений.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Awaitable, Dict, Any


class RateLimitMiddleware(BaseMiddleware):
        
    def __init__(self):
        """Инициализирует middleware с настройками rate limiting."""
        self.requests: Dict[int, list] = defaultdict(list)
        """Словарь с временными метками запросов по user_id."""
        
        self.max_requests = 30
        """Максимальное количество запросов в временном окне."""
        
        self.time_window = timedelta(minutes=1)
        """Временное окно для подсчета запросов."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Обрабатывает событие и проверяет rate limit.
        
        Извлекает user_id из события, проверяет количество запросов
        в текущем временном окне. Если лимит превышен - блокирует обработку.
        
        Args:
            handler (Callable): Следующий обработчик в цепочке middleware
            event (TelegramObject): Событие от Telegram (Message, CallbackQuery и т.д.)
            data (Dict[str, Any]): Данные для передачи между middleware
            
        Returns:
            Any: Результат обработки handler или None если лимит превышен
            
        Note:
            Поддерживает извлечение user_id из различных типов событий:
            Message, CallbackQuery и других объектов с from_user.
        """
        # Получаем user_id из события
        user_id = None
        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id
        elif hasattr(event, 'message') and event.message and event.message.from_user:
            user_id = event.message.from_user.id
        elif hasattr(event, 'callback_query') and event.callback_query:
            user_id = event.callback_query.from_user.id
        
        if user_id:
            now = datetime.utcnow()
            
            # Очищаем старые запросы
            self.requests[user_id] = [
                req_time for req_time in self.requests[user_id]
                if now - req_time < self.time_window
            ]
            
            # Проверяем лимит
            if len(self.requests[user_id]) >= self.max_requests:
                # Превышен лимит - не обрабатываем запрос
                if hasattr(event, 'answer') and callable(event.answer):
                    try:
                        await event.answer("Превышен лимит запросов. Подожди минуту.")
                    except:
                        pass
                return
            
            # Добавляем текущий запрос
            self.requests[user_id].append(now)
        
        # Продолжаем обработку
        return await handler(event, data)

