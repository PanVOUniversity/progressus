"""FastAPI приложение с webhook для Telegram бота.

Модуль создает FastAPI приложение, которое работает как webhook сервер
для Telegram бота или запускает polling режим. Управляет жизненным циклом
бота, создает таблицы БД и обрабатывает входящие обновления от Telegram.
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Header
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands
from aiogram.fsm.storage.redis import RedisStorage
from app.config import settings
from app.handlers import start, privacy, survey, payments, reports, referral, restart, menu, voice, personalization
from app.database import engine, Base

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
dp.include_router(survey.router)
dp.include_router(payments.router)
dp.include_router(voice.router)  # Обработчик голосовых сообщений
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


@app.get("/health")
async def health_check():
    """Health check endpoint для проверки работоспособности сервиса.
    
    Returns:
        dict: Словарь со статусом {"status": "ok"}
    """
    return {"status": "ok"}


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
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"ok": False, "error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development"
    )

