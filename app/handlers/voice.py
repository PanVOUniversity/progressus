"""Handler для обработки голосовых сообщений.

Модуль обрабатывает голосовые сообщения от пользователей, распознает их
через Yandex SpeechKit и отправляет распознанный текст как обычное текстовое сообщение.
"""
import io
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import httpx
from app.config import settings
from app.states import SurveyStates

logger = logging.getLogger(__name__)

router = Router()
"""Роутер для обработки голосовых сообщений."""


# Состояния опроса с кнопками, где голосовые сообщения не должны обрабатываться
SURVEY_BUTTON_STATES = {
    SurveyStates.gender,
    SurveyStates.values,
    SurveyStates.development_spheres,
    SurveyStates.role_model,
    SurveyStates.privacy_consent,
}




@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext):
    """Обработка голосовых сообщений от пользователей.
    
    Распознает голосовое сообщение через Yandex SpeechKit и отправляет
    распознанный текст как обычное текстовое сообщение для обработки
    существующими обработчиками.
    
    Args:
        message (Message): Голосовое сообщение от пользователя
        state (FSMContext): Контекст FSM для проверки состояния
    """
    # Проверяем, не находимся ли мы в состоянии опроса с кнопками
    current_state = await state.get_state()
    if current_state in SURVEY_BUTTON_STATES:
        # В состоянии опроса с кнопками не обрабатываем голосовые сообщения
        return
    
    voice = message.voice
    
    # Скачиваем голосовое сообщение
    try:
        file = await message.bot.get_file(voice.file_id)
        voice_bytes = io.BytesIO()
        await message.bot.download_file(file.file_path, voice_bytes)
        voice_bytes.seek(0)
        voice_data = voice_bytes.read()
    except Exception as e:
        logger.error(f"Ошибка скачивания голосового сообщения: {e}")
        await message.answer("❌ Ошибка при обработке голосового сообщения")
        return
    
    # Проверяем наличие API ключа
    if not settings.YANDEX_SPEECHKIT_API_KEY:
        logger.error("Не указан API ключ для Yandex SpeechKit")
        await message.answer("❌ Ошибка: не настроен Yandex SpeechKit (отсутствует API ключ)")
        return
    
    # Отправляем на Yandex SpeechKit для распознавания
    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    
    # Используем API ключ напрямую через заголовок Api-Key
    headers = {
        "Authorization": f"Api-Key {settings.YANDEX_SPEECHKIT_API_KEY}",
        "Content-Type": "application/octet-stream"
    }
    
    # Параметры для распознавания речи
    # Для формата oggopus sampleRateHertz не нужен, определяется автоматически
    params = {
        "lang": "ru-RU",
        "format": "oggopus"  # Формат Telegram voice (OGG OPUS)
    }
    
    try:
        logger.info(f"Отправляем запрос к SpeechKit. Размер аудио: {len(voice_data)} байт, параметры: {params}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                content=voice_data,
                timeout=30.0
            )
            
            logger.info(f"Ответ от SpeechKit: статус {response.status_code}")
            
            # Проверяем статус ответа перед парсингом JSON
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"SpeechKit вернул ошибку {response.status_code}: {error_text}")
                await message.answer(f"❌ Ошибка распознавания (HTTP {response.status_code}). Проверьте логи.")
                return
            
            try:
                result = response.json()
                logger.info(f"Результат от SpeechKit: {result}")
            except Exception as json_error:
                logger.error(f"Ошибка парсинга JSON ответа: {json_error}, тело ответа: {response.text}")
                await message.answer("❌ Ошибка при обработке ответа от SpeechKit")
                return
            
            if "result" in result:
                text = result["result"]
                if text and text.strip():
                    logger.info(f"Распознанный текст: {text}")
                    # Отправляем распознанный текст пользователю
                    await message.answer(f"🎤 Распознано: {text}")
                    
                    # Создаем новое текстовое сообщение с распознанным текстом
                    # и обрабатываем его через диспетчер
                    from aiogram.types import Update
                    from app.main import dp
                    
                    # Создаем новое сообщение с распознанным текстом
                    # Копируем структуру исходного сообщения, но заменяем voice на text
                    message_dict = message.model_dump(mode='json')
                    message_dict["text"] = text
                    # Удаляем voice из сообщения
                    if "voice" in message_dict:
                        del message_dict["voice"]
                    
                    # Создаем Update объект с новым текстовым сообщением
                    # Используем уникальный update_id чтобы избежать конфликтов
                    import time
                    update_data = {
                        "update_id": int(time.time() * 1000000) + message.message_id,
                        "message": message_dict
                    }
                    
                    # Обрабатываем через диспетчер
                    try:
                        update = Update(**update_data)
                        await dp.feed_update(message.bot, update)
                        logger.info("Распознанный текст успешно обработан через диспетчер")
                    except Exception as e:
                        logger.error(f"Ошибка при обработке распознанного текста: {e}", exc_info=True)
                        # Если не удалось обработать через диспетчер, просто отправляем текст
                        # и пользователь может отправить его вручную
                else:
                    logger.warning("SpeechKit вернул пустой результат")
                    await message.answer("❌ Не удалось распознать речь. Попробуйте еще раз.")
            else:
                logger.error(f"SpeechKit вернул неожиданный формат ответа: {result}")
                await message.answer("❌ Ошибка распознавания речи")
                
    except httpx.HTTPStatusError as e:
        error_response = ""
        try:
            error_response = e.response.text
        except:
            pass
        logger.error(f"HTTP ошибка при распознавании речи: {e.response.status_code} - {error_response}")
        await message.answer(f"❌ Ошибка при распознавании речи (HTTP {e.response.status_code}). Проверьте логи.")
    except Exception as e:
        logger.error(f"Ошибка при распознавании речи: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")

