"""Сервис для работы с YooKassa API.

Модуль содержит функции для создания платежей через YooKassa API
с поддержкой СБП (Система быстрых платежей).
"""
import logging
import asyncio
from typing import Optional
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotificationFactory
from yookassa.domain.request import PaymentRequest
from app.config import settings

logger = logging.getLogger(__name__)


def configure_yookassa():
    """Настраивает YooKassa API с учетными данными из настроек.
    
    Вызывается при первом использовании API для инициализации
    shop_id и secret_key.
    """
    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        logger.warning("YooKassa credentials not configured")
        return False
    
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    return True


async def create_sbp_payment(
    amount: int,
    user_id: int,
    description: str = "Premium доступ",
    return_url: Optional[str] = None,
    message_id: Optional[int] = None,
    chat_id: Optional[int] = None
) -> Optional[dict]:
    """Создает платеж через YooKassa с методом оплаты СБП.
    
    Args:
        amount (int): Сумма платежа в копейках
        user_id (int): Telegram ID пользователя
        description (str): Описание платежа
        return_url (Optional[str]): URL для возврата после оплаты
        
    Returns:
        Optional[dict]: Словарь с данными платежа:
            - id: ID платежа в YooKassa
            - confirmation_url: URL для оплаты
            - status: Статус платежа
        Или None в случае ошибки
    """
    if not configure_yookassa():
        logger.error("YooKassa not configured")
        return None
    
    # Формируем webhook URL
    webhook_url = None
    if settings.YOOKASSA_WEBHOOK_URL:
        webhook_url = settings.YOOKASSA_WEBHOOK_URL
    elif settings.WEBHOOK_URL:
        webhook_url = f"{settings.WEBHOOK_URL}/yookassa/webhook"
    
    # Формируем return_url для возврата в бота
    if not return_url:
        if settings.BOT_USERNAME:
            return_url = f"https://t.me/{settings.BOT_USERNAME}"
        else:
            return_url = "https://t.me"
    
    try:
        # Создаем запрос на платеж
        payment_request = PaymentRequest({
            "amount": {
                "value": f"{amount / 100:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": str(user_id),
                **({"message_id": str(message_id), "chat_id": str(chat_id)} if message_id and chat_id else {})
            },
            "payment_method_data": {
                "type": "sbp"
            },
            "save_payment_method": False
        })
        
        # Добавляем webhook URL если указан
        if webhook_url:
            payment_request.notification_url = webhook_url
        
        # Создаем платеж (синхронный вызов в executor)
        loop = asyncio.get_event_loop()
        payment = await loop.run_in_executor(None, Payment.create, payment_request)
        
        logger.info(f"Created YooKassa payment {payment.id} for user {user_id}, amount: {amount}")
        
        return {
            "id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url if payment.confirmation else None,
            "status": payment.status,
            "amount": payment.amount.value,
            "currency": payment.amount.currency
        }
    except Exception as e:
        logger.error(f"Error creating YooKassa payment for user {user_id}: {e}", exc_info=True)
        return None


async def get_payment_status(payment_id: str) -> Optional[dict]:
    """Получает статус платежа по ID.
    
    Args:
        payment_id (str): ID платежа в YooKassa
        
    Returns:
        Optional[dict]: Словарь с данными платежа или None в случае ошибки
    """
    if not configure_yookassa():
        return None
    
    try:
        # Синхронный вызов в executor
        loop = asyncio.get_event_loop()
        payment = await loop.run_in_executor(None, Payment.find_one, payment_id)
        return {
            "id": payment.id,
            "status": payment.status,
            "paid": payment.paid,
            "amount": payment.amount.value,
            "currency": payment.amount.currency,
            "metadata": payment.metadata
        }
    except Exception as e:
        logger.error(f"Error getting payment status for {payment_id}: {e}", exc_info=True)
        return None


def parse_webhook_notification(request_body: dict) -> Optional[dict]:
    """Парсит webhook уведомление от YooKassa.
    
    Args:
        request_body (dict): Тело запроса от YooKassa
        
    Returns:
        Optional[dict]: Словарь с данными уведомления:
            - event: Тип события (payment.succeeded, payment.canceled и т.д.)
            - payment_id: ID платежа
            - status: Статус платежа
            - user_id: ID пользователя из metadata
        Или None в случае ошибки
    """
    try:
        notification = WebhookNotificationFactory().create(request_body)
        payment_object = notification.object
        
        metadata = payment_object.metadata if payment_object.metadata else {}
        return {
            "event": notification.event,
            "payment_id": payment_object.id,
            "status": payment_object.status,
            "paid": payment_object.paid,
            "amount": payment_object.amount.value,
            "currency": payment_object.amount.currency,
            "user_id": metadata.get("user_id"),
            "message_id": metadata.get("message_id"),
            "chat_id": metadata.get("chat_id")
        }
    except Exception as e:
        logger.error(f"Error parsing YooKassa webhook: {e}", exc_info=True)
        return None

