"""Handler для обработки голосовых сообщений.

Модуль обрабатывает голосовые сообщения от пользователей, распознает их
через Yandex SpeechKit и отправляет распознанный текст как обычное текстовое сообщение.
"""
import io
import logging
import tempfile
import os
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import httpx
from pydub import AudioSegment
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

# Максимальная длительность для синхронного распознавания Yandex SpeechKit
# Используем 25 секунд для запаса, так как Yandex может определять длительность по-другому
# и даже 28 секунд могут считаться >= 30 секунд
MAX_SYNC_DURATION = 25  # секунд (берем 25 для надежности, так как Yandex требует строго < 30s)


async def recognize_audio_chunk(audio_data: bytes, audio_format: str = "oggopus") -> str:
    """Распознает один фрагмент аудио через Yandex SpeechKit.
    
    Args:
        audio_data (bytes): Данные аудиофайла
        audio_format (str): Формат аудио (oggopus, m4a, mp3 и т.д.)
        
    Returns:
        str: Распознанный текст
        
    Raises:
        Exception: При ошибке распознавания
    """
    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    
    headers = {
        "Authorization": f"Api-Key {settings.YANDEX_SPEECHKIT_API_KEY}",
        "Content-Type": "application/octet-stream"
    }
    
    params = {
        "lang": "ru-RU",
        "format": audio_format
    }
    
    # Для формата LPCM нужно указать sampleRateHertz
    if audio_format == "lpcm":
        params["sampleRateHertz"] = "16000"  # 16kHz - стандарт для распознавания речи
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            params=params,
            headers=headers,
            content=audio_data,
            timeout=30.0
        )
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"SpeechKit вернул ошибку {response.status_code}: {error_text}")
            raise Exception(f"SpeechKit error {response.status_code}: {error_text}")
        
        result = response.json()
        if "result" in result:
            recognized_text = result["result"].strip()
            if recognized_text:
                return recognized_text
            else:
                return ""  # Возвращаем пустую строку вместо исключения
        else:
            logger.error(f"Unexpected response format: {result}")
            raise Exception(f"Unexpected response format: {result}")


async def split_and_recognize_audio(voice_data: bytes, duration_seconds: int, mime_type: str = None) -> str:
    """Разбивает длинное аудио на части и распознает каждую часть.
    
    Args:
        voice_data (bytes): Данные аудиофайла
        duration_seconds (int): Длительность аудио в секундах (может быть 0 или None)
        mime_type (str): MIME тип аудио (опционально)
        
    Returns:
        str: Объединенный распознанный текст всех частей
    """
    # Определяем формат на основе mime_type
    audio_format = "oggopus"  # По умолчанию
    if mime_type:
        if "m4a" in mime_type.lower() or "aac" in mime_type.lower():
            audio_format = "m4a"
        elif "mp3" in mime_type.lower():
            audio_format = "mp3"
        elif "wav" in mime_type.lower():
            audio_format = "lpcm"
    
    # Сохраняем во временный файл для обработки pydub
    with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_input:
        temp_input.write(voice_data)
        temp_input_path = temp_input.name
    
    try:
        # Загружаем аудио через pydub для получения реальной длительности
        audio = AudioSegment.from_file(temp_input_path, format="ogg")
        total_duration_ms = len(audio)
        total_duration_seconds = total_duration_ms / 1000.0
        
        # Если аудио короткое, распознаем целиком
        if total_duration_seconds <= MAX_SYNC_DURATION:
            return await recognize_audio_chunk(voice_data, audio_format)
        
        # Вычисляем количество частей
        chunk_duration_ms = MAX_SYNC_DURATION * 1000  # в миллисекундах
        num_chunks = (total_duration_ms + chunk_duration_ms - 1) // chunk_duration_ms
        
        recognized_texts = []
        
        # Обрабатываем каждую часть
        for i in range(num_chunks):
            start_ms = i * chunk_duration_ms
            end_ms = min((i + 1) * chunk_duration_ms, total_duration_ms)
            
            chunk = audio[start_ms:end_ms]
            
            # Проверяем длительность чанка перед экспортом
            chunk_duration_sec = len(chunk) / 1000.0
            if chunk_duration_sec >= 30.0:
                logger.warning(f"Часть {i+1} слишком длинная ({chunk_duration_sec:.2f} сек), обрезаем до {MAX_SYNC_DURATION} сек")
                # Обрезаем до максимальной длительности
                chunk = chunk[:MAX_SYNC_DURATION * 1000]
                chunk_duration_sec = len(chunk) / 1000.0
            
            # Сохраняем часть во временный файл
            # Пробуем экспортировать в LPCM (WAV), так как OGG может иметь проблемы с определением длительности
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_chunk:
                # Экспортируем в WAV (LPCM) с явными параметрами
                # Экспортируем в WAV (LPCM) с явными параметрами
                # Используем 16kHz, моно, 16-bit PCM - стандарт для распознавания речи
                chunk.export(
                    temp_chunk.name, 
                    format="wav",
                    parameters=["-ar", "16000", "-ac", "1", "-sample_fmt", "s16"]  # 16kHz, моно, 16-bit
                )
                temp_chunk_path = temp_chunk.name
            
            try:
                # Проверяем длительность экспортированного файла
                exported_audio = AudioSegment.from_file(temp_chunk_path, format="wav")
                exported_duration_sec = len(exported_audio) / 1000.0
                
                if exported_duration_sec >= 30.0:
                    logger.error(f"Часть {i+1} после экспорта все еще слишком длинная ({exported_duration_sec:.2f} сек), пропускаем")
                    continue
                
                # Читаем данные части
                with open(temp_chunk_path, 'rb') as f:
                    chunk_data = f.read()
                
                # Используем формат lpcm для WAV файлов
                recognition_format = "lpcm" if audio_format == "oggopus" else audio_format
                
                # Распознаем часть
                chunk_text = await recognize_audio_chunk(chunk_data, recognition_format)
                
                if chunk_text:
                    recognized_texts.append(chunk_text)
                    
            except Exception as e:
                logger.error(f"Ошибка при распознавании части {i+1}: {e}")
                # Продолжаем обработку остальных частей
            finally:
                # Удаляем временный файл части
                if os.path.exists(temp_chunk_path):
                    os.unlink(temp_chunk_path)
        
        # Проверяем, что хотя бы одна часть была распознана
        if not recognized_texts:
            raise Exception(f"Не удалось распознать ни одну часть из {num_chunks}")
        
        # Объединяем все распознанные тексты
        full_text = " ".join(recognized_texts)
        
        return full_text
        
    finally:
        # Удаляем временный входной файл
        if os.path.exists(temp_input_path):
            os.unlink(temp_input_path)


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
    
    # Распознаем аудио (с автоматической разбивкой на части, если нужно)
    try:
        # Показываем сообщение о начале обработки
        if voice.duration and voice.duration > MAX_SYNC_DURATION:
            await message.answer(f"⏳ Обрабатываю длинное сообщение ({voice.duration} сек), это может занять время...")
        else:
            await message.answer("⏳ Распознаю голосовое сообщение...")
        
        text = await split_and_recognize_audio(
            voice_data, 
            voice.duration or 0,
            voice.mime_type
        )
        
        if text and text.strip():
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
            except Exception as e:
                logger.error(f"Ошибка при обработке распознанного текста через диспетчер: {e}", exc_info=True)
                # Если не удалось обработать через диспетчер, пытаемся напрямую вызвать обработчики
                current_state = await state.get_state()
                
                try:
                    # Прямая обработка для состояний опроса
                    # Создаем временное сообщение с текстом
                    from aiogram.types import Message as MessageType
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
                except Exception as direct_error:
                    logger.error(f"Ошибка при прямой обработке: {direct_error}", exc_info=True)
        else:
            await message.answer("❌ Не удалось распознать речь. Попробуйте еще раз.")
            return
                
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

