"""FastAPI приложение с webhook для Telegram бота.

Модуль создает FastAPI приложение, которое работает как webhook сервер
для Telegram бота или запускает polling режим. Управляет жизненным циклом
бота, создает таблицы БД и обрабатывает входящие обновления от Telegram.
"""
import logging
import asyncio
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.exceptions import TelegramBadRequest
from app.config import settings
from app.handlers import start, privacy, survey, payments, reports, referral, restart, menu, voice, personalization
from app.database import engine, Base, get_db, async_session_maker
from app.services.yookassa_service import parse_webhook_notification
from app.services.user_service import activate_premium
from app.services.referral_service import add_referral_on_payment
from app.models import Payment, User
from sqlalchemy import select, update

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
"""Логгер для модуля main."""

# Инициализация бота и диспетчера
bot = Bot(token=settings.BOT_TOKEN)
"""Экземпляр Telegram бота."""

storage = RedisStorage.from_url(settings.REDIS_URL)
"""Хранилище состояний FSM в Redis."""

dp = Dispatcher(storage=storage)
"""Диспетчер для обработки обновлений от Telegram."""

# Регистрируем Bot для dependency injection в обработчиках
dp["bot"] = bot

# Регистрация middleware
from app.middleware.rate_limit import RateLimitMiddleware
dp.message.middleware(RateLimitMiddleware())
dp.callback_query.middleware(RateLimitMiddleware())

# Регистрация роутеров
# Команды регистрируем первыми, чтобы они обрабатывались раньше общих текстовых обработчиков
dp.include_router(start.router)
dp.include_router(restart.router)  # Рестарт должен быть раньше, чтобы перехватывать кнопку рестарта
dp.include_router(menu.router)  # Меню должно быть после start, но до других обработчиков
dp.include_router(referral.router)
dp.include_router(privacy.router)
dp.include_router(voice.router)  # Обработчик голосовых сообщений - должен быть ДО survey.router
dp.include_router(survey.router)
dp.include_router(payments.router)
dp.include_router(personalization.router)  # Обработчик персонализации
dp.include_router(reports.router)


async def setup_bot_commands(bot: Bot):
    """Устанавливает команды бота и настраивает меню.
    
    Устанавливает список команд, которые будут отображаться когда пользователь
    набирает "/" в чате с ботом, и настраивает постоянную кнопку меню.
    
    Args:
        bot (Bot): Экземпляр Telegram бота
    """
    commands = [
        BotCommand(command="restart", description="� Рестарт бота (сброс данных) кроме "),
        BotCommand(command="menu", description="Главное меню"),
    ]
    
    # Устанавливаем команды бота
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("Bot commands set successfully")
    
    # Настраиваем меню команд (постоянная кнопка Menu)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("Menu button configured successfully")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения.
    
    Выполняет инициализацию при старте приложения:
    - Создает таблицы БД
    - Устанавливает webhook или запускает polling
    
    При остановке приложения:
    - Останавливает polling (если был запущен)
    - Закрывает сессию бота
    
    Args:
        app (FastAPI): Экземпляр FastAPI приложения
        
    Yields:
        None: Контроль возвращается приложению
    """
    # Startup
    logger.info("Starting bot...")
    
    # Создаем таблицы БД
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Устанавливаем команды бота и меню
    await setup_bot_commands(bot)
    
    # Устанавливаем webhook если указан URL, иначе запускаем polling
    polling_task = None
    if settings.WEBHOOK_URL:
        webhook_url = f"{settings.WEBHOOK_URL}/webhook"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.WEBHOOK_SECRET
        )
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.info("Webhook URL not set, starting polling mode")
        # Запускаем polling в фоновой задаче
        polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        logger.info("Polling started")
    
    yield
    
    # Shutdown: останавливаем polling если был запущен
    if polling_task is not None:
        logger.info("Stopping polling...")
        await dp.stop_polling()
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    
    # Shutdown
    logger.info("Shutting down bot...")
    await bot.session.close()


# Создаем FastAPI приложение
app = FastAPI(title="Progressusbot", lifespan=lifespan)
"""FastAPI приложение для работы Telegram бота."""

# Настройка CORS для админки
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://progressusbot.ru",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Обработчик исключений для возврата JSON вместо HTML
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации - возвращает JSON вместо HTML."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Ошибка валидации запроса", "details": str(exc)}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений - возвращает JSON вместо HTML."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик всех остальных исключений - возвращает JSON вместо HTML."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": f"Внутренняя ошибка сервера: {str(exc)}"}
    )

# Создаем директорию для отчетов, если её нет
reports_dir = "reports"
os.makedirs(reports_dir, exist_ok=True)

# Подключаем статику для скачивания файлов
# Используем html=True чтобы показывать список файлов при обращении к директории
app.mount("/reports", StaticFiles(directory=reports_dir, html=True), name="reports")


@app.get("/health")
async def health_check():
    """Health check endpoint для проверки работоспособности сервиса.
    
    Returns:
        dict: Словарь со статусом {"status": "ok"}
    """
    return {"status": "ok"}


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Админ панель для генерации отчетов.
    
    Returns:
        HTMLResponse: HTML страница с формой для ввода периода
    """
    with open("app/templates/admin.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Устанавливаем заголовки CSP для админки
    # Разрешаем inline скрипты (наш JavaScript в HTML), но запрещаем eval()
    response = HTMLResponse(content=html_content)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response


@app.get("/oferta", response_class=HTMLResponse)
async def oferta_page(request: Request):
    """Страница с публичной офертой сервиса.
    
    Returns:
        HTMLResponse: HTML страница с текстом публичной оферты
    """
    with open("app/templates/oferta.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    response = HTMLResponse(content=html_content)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "frame-ancestors 'none';"
    )
    return response


@app.post("/admin/generate-report", response_class=JSONResponse)
async def generate_report(request: Request):
    """Генерирует Excel отчет за указанный период.
    
    Args:
        request (Request): FastAPI request с JSON телом:
            {
                "startDate": "dd.mm.yy",
                "endDate": "dd.mm.yy"
            }
    
    Returns:
        JSONResponse: Ответ с URL для скачивания файла или ошибкой
    """
    try:
        # Пытаемся получить JSON данные
        try:
            data = await request.json()
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": f"Ошибка при парсинге JSON: {str(e)}"}
            )
        start_date_str = data.get("startDate")
        end_date_str = data.get("endDate")
        
        if not start_date_str or not end_date_str:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Не указаны даты начала и конца периода"}
            )
        
        # Парсим даты из формата dd.mm.yy
        try:
            start_date = datetime.strptime(start_date_str, "%d.%m.%y")
            end_date = datetime.strptime(end_date_str, "%d.%m.%y")
            
            # Устанавливаем время начала на 00:00:00, конца на 23:59:59
            # Добавляем timezone UTC для совместимости с БД
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
            
            if start_date > end_date:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Дата начала не может быть позже даты конца"}
                )
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": f"Неверный формат даты. Используйте формат dd.mm.yy: {str(e)}"}
            )
        
        # Генерируем имя файла
        filename = f"report_{start_date_str}_{end_date_str}.xlsx"
        filepath = os.path.join(reports_dir, filename)
        
        # Убеждаемся, что директория существует
        try:
            os.makedirs(reports_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creating reports directory: {e}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": f"Ошибка при создании директории для отчетов: {str(e)}"}
            )
        
        # Генерируем отчет
        try:
            from app.services.report_generator import generate_excel_report
            
            # Создаем сессию БД напрямую
            async with async_session_maker() as session:
                try:
                    logger.info(f"Starting report generation: {start_date} to {end_date}, file: {filepath}")
                    await generate_excel_report(session, start_date, end_date, filepath)
                    logger.info(f"Report generated successfully: {filepath}")
                except Exception as e:
                    logger.error(f"Error in generate_excel_report: {e}", exc_info=True)
                    await session.rollback()
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"error": f"Ошибка при генерации Excel файла: {str(e)}"}
                    )
        except Exception as e:
            logger.error(f"Error getting database session or generating report: {e}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": f"Ошибка при генерации отчета: {str(e)}"}
            )
        
        # Проверяем, что файл создан
        if not os.path.exists(filepath):
            logger.error(f"Report file was not created: {filepath}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Файл отчета не был создан"}
            )
        
        # Возвращаем URL для скачивания
        download_url = f"/reports/{filename}"
        logger.info(f"Report ready for download: {download_url}")
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"downloadUrl": download_url}
        )
        response.headers["Content-Type"] = "application/json"
        return response
        
    except Exception as e:
        logger.error(f"Unexpected error generating report: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Неожиданная ошибка при генерации отчета: {str(e)}"}
        )


@app.post("/webhook")
async def webhook_handler(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """Webhook endpoint для получения обновлений от Telegram.
    
    Обрабатывает POST запросы от Telegram с обновлениями бота.
    Проверяет secret token (если указан) и передает обновление
    в диспетчер для обработки.
    
    Args:
        request (Request): FastAPI request объект с телом запроса
        x_telegram_bot_api_secret_token (Optional[str]): Secret token из заголовка
        
    Returns:
        JSONResponse: Ответ Telegram API:
            - {"ok": True} при успешной обработке
            - {"ok": False, "error": "..."} при ошибке
            
    Note:
        Если WEBHOOK_SECRET указан в настройках, запросы без правильного
        токена будут отклонены с кодом 403.
    """
    try:
        # Проверка secret token если указан
        if settings.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"ok": False, "error": "Invalid secret token"}
            )
        
        # Получаем данные запроса
        data = await request.json()
        
        # Создаем Update объект
        update = types.Update(**data)
        
        # Обрабатываем через диспетчер
        await dp.feed_update(bot, update)
        
        return JSONResponse(status_code=status.HTTP_200_OK, content={"ok": True})
    except TelegramBadRequest as e:
        # Обрабатываем ошибки Telegram API (например, устаревшие callback queries)
        error_msg = str(e)
        if "query is too old" in error_msg or "query ID is invalid" in error_msg:
            logger.debug(f"Telegram API error (likely expired callback): {error_msg}")
        else:
            logger.warning(f"Telegram API error: {error_msg}")
        # Все равно возвращаем 200 OK, чтобы Telegram не повторял запрос
        return JSONResponse(status_code=status.HTTP_200_OK, content={"ok": True})
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"ok": False, "error": str(e)}
        )


@app.post("/yookassa/webhook")
async def yookassa_webhook_handler(request: Request):
    """Webhook endpoint для получения уведомлений от YooKassa.
    
    Обрабатывает POST запросы от YooKassa с уведомлениями о статусе платежей.
    При успешной оплате активирует premium доступ пользователю.
    
    Args:
        request (Request): FastAPI request объект с телом запроса от YooKassa
        
    Returns:
        JSONResponse: Ответ YooKassa API (обычно пустой ответ со статусом 200)
    """
    try:
        # Получаем данные запроса
        data = await request.json()
        
        # Парсим уведомление
        notification = parse_webhook_notification(data)
        
        if not notification:
            logger.warning("Failed to parse YooKassa webhook notification")
            return JSONResponse(status_code=status.HTTP_200_OK, content={})
        
        payment_id = notification.get("payment_id")
        event = notification.get("event")
        user_id_str = notification.get("user_id")
        
        logger.info(f"YooKassa webhook: event={event}, payment_id={payment_id}, user_id={user_id_str}")
        
        # Обрабатываем только успешные платежи
        if event == "payment.succeeded" and notification.get("paid"):
            if not user_id_str:
                logger.warning(f"User ID not found in payment metadata for payment {payment_id}")
                return JSONResponse(status_code=status.HTTP_200_OK, content={})
            
            try:
                user_id = int(user_id_str)
            except (ValueError, TypeError):
                logger.error(f"Invalid user_id in payment metadata: {user_id_str}")
                return JSONResponse(status_code=status.HTTP_200_OK, content={})
            
            # Проверяем, не обработан ли уже этот платеж
            async for session in get_db():
                try:
                    # Проверяем, существует ли уже платеж с таким payment_id
                    result = await session.execute(
                        select(Payment).where(Payment.payment_id == payment_id)
                    )
                    existing_payment = result.scalar_one_or_none()
                    
                    if existing_payment:
                        logger.info(f"Payment {payment_id} already processed")
                        break
                    
                    # Сохраняем платеж в БД
                    amount = int(float(notification.get("amount", 0)) * 100)  # Конвертируем в копейки
                    db_payment = Payment(
                        user_id=user_id,
                        payment_id=payment_id,
                        amount=amount,
                        status="completed"
                    )
                    session.add(db_payment)
                    
                    # Активируем premium на 1 месяц
                    await activate_premium(session, user_id, months=1)
                    
                    # Повышаем уровень до 1 при первой оплате
                    result = await session.execute(select(User).where(User.user_id == user_id))
                    user = result.scalar_one_or_none()
                    
                    if user and user.level == 0:
                        await session.execute(
                            update(User)
                            .where(User.user_id == user_id)
                            .values(level=1)
                        )
                    
                    # Обрабатываем рефералку
                    referrer_id = await add_referral_on_payment(session, user_id)
                    if referrer_id:
                        # Даем месяц бесплатного премиума рефереру
                        await activate_premium(session, referrer_id, months=1)
                        logger.info(f"Активирован premium для реферера {referrer_id} за оплату пользователя {user_id}")
                    
                    await session.commit()
                    
                    # Получаем message_id и chat_id из metadata для удаления сообщения
                    message_id = notification.get("message_id")
                    chat_id = notification.get("chat_id")
                    
                    # Удаляем сообщение с предложением оплаты, если есть message_id
                    if message_id and chat_id:
                        try:
                            await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
                            logger.info(f"Deleted payment message {message_id} for user {user_id}")
                        except Exception as e:
                            logger.warning(f"Failed to delete payment message {message_id} for user {user_id}: {e}")
                    
                    # Отправляем сообщение об успешной оплате
                    try:
                        await bot.send_message(
                            user_id,
                            "✅ Успешно оплачено!\n\n"
                            "Premium доступ активирован."
                        )
                        
                        # Проверяем, прошел ли пользователь опрос
                        if not user.goal_3months and not user.roadmap:
                            # Пользователь еще не прошел опрос - начинаем опрос
                            from app.keyboards import get_gender_keyboard, get_main_keyboard
                            from app.states import SurveyStates
                            
                            await bot.send_message(
                                user_id,
                                "👋 Привет! Ты попал в пространство развития Progressus.\n\n"
                                "📈 Progressus - твой лучший персональный наставник.\n\n"
                                "✨ Топовые ролевые модели\n"
                                "📝 Персональные задания\n\n"
                                "Именно здесь ты реализуешь весь свой потенциал, но для начала "
                                "давай пройдем небольшой опрос, чтобы лучше тебя понять.\n\n"
                                "Твой пол?",
                                reply_markup=get_gender_keyboard()
                            )
                            await bot.send_message(
                                user_id,
                                "",
                                reply_markup=get_main_keyboard()
                            )
                        else:
                            # Пользователь уже прошел опрос - показываем меню
                            from app.keyboards import get_main_menu_keyboard
                            
                            # Формируем текст меню
                            user_name = user.name if user and user.name else None
                            if user_name:
                                menu_text = f"👋 Привет, {user_name}!\n\n"
                            else:
                                menu_text = "👋 Привет!\n\n"
                            menu_text += "📈 Progressus - твой лучший персональный наставник.\n\n"
                            menu_text += "✨ Топовые ролевые модели\n"
                            menu_text += "📝 Персональные задания\n\n"
                            menu_text += "🎁 За 3 оплативших реферала - месяц Premium в подарок!"
                            
                            # Отправляем меню
                            await bot.send_message(
                                user_id,
                                menu_text,
                                reply_markup=get_main_menu_keyboard()
                            )
                        
                    except Exception as e:
                        logger.warning(f"Failed to send notification to user {user_id}: {e}")
                    
                    logger.info(f"Successfully processed YooKassa payment {payment_id} for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing YooKassa payment {payment_id}: {e}", exc_info=True)
                    await session.rollback()
                break
        
        # Всегда возвращаем 200 OK для YooKassa
        return JSONResponse(status_code=status.HTTP_200_OK, content={})
        
    except Exception as e:
        logger.error(f"YooKassa webhook error: {e}", exc_info=True)
        # YooKassa требует 200 OK даже при ошибках
        return JSONResponse(status_code=status.HTTP_200_OK, content={})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development"
    )

