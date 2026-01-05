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
                    try:
                        from aiogram.types import Update, Message as MessageType
                        from app.main import dp
                        import time
                        
                        # Создаем новое сообщение с текстом на основе исходного
                        # Используем model_copy для создания копии, исключая voice и другие медиа
                        message_dict = message.model_dump(exclude={'voice', 'audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'animation'})
                        message_dict["text"] = text
                        # Убеждаемся, что message_id уникальный
                        message_dict["message_id"] = message.message_id + 1000000
                        
                        # Создаем новое сообщение из словаря
                        new_message = MessageType(**message_dict)
                        
                        # Создаем Update с новым сообщением
                        update = Update(
                            update_id=int(time.time() * 1000000) + message.message_id,
                            message=new_message
                        )
                        
                        # Обрабатываем через диспетчер
                        await dp.feed_update(message.bot, update)
                        logger.info("Распознанный текст успешно обработан через диспетчер")
                    except Exception as e:
                        logger.error(f"Ошибка при обработке распознанного текста через диспетчер: {e}", exc_info=True)
                        # Если не удалось обработать через диспетчер, пытаемся напрямую вызвать обработчики
                        current_state = await state.get_state()
                        logger.info(f"Попытка прямой обработки текста в состоянии {current_state}")
                        
                        try:
                            # Прямая обработка для состояний опроса
                            # Создаем временное сообщение с текстом
                            temp_dict = message.model_dump()
                            temp_dict["text"] = text
                            if "voice" in temp_dict:
                                del temp_dict["voice"]
                            # Удаляем другие медиа-поля
                            for field in ["audio", "document", "photo", "sticker", "video", "video_note", "animation"]:
                                if field in temp_dict:
                                    del temp_dict[field]
                            
                            temp_message = MessageType(**temp_dict)
                            
                            if current_state == SurveyStates.age:
                                from app.handlers.survey import process_age
                                await process_age(temp_message, state)
                            elif current_state == SurveyStates.name:
                                from app.handlers.survey import process_name
                                await process_name(temp_message, state)
                            elif current_state == SurveyStates.goal_3months:
                                from app.handlers.survey import process_goal_3months
                                await process_goal_3months(temp_message, state)
                            elif current_state == SurveyStates.detailed_questions:
                                from app.handlers.survey import process_detailed_answer
                                await process_detailed_answer(temp_message, state)
                            else:
                                logger.warning(f"Неизвестное состояние для обработки голосового: {current_state}")
                        except Exception as direct_error:
                            logger.error(f"Ошибка при прямой обработке: {direct_error}", exc_info=True)
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

