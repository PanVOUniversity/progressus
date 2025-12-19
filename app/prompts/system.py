"""Системный промпт для AI-коуча.

Модуль содержит системный промпт для создания модели пользователя
и роадмапа достижения цели.
"""
import os
from pathlib import Path

# Загружаем промпт из текстового файла
PROMPT_FILE = Path(__file__).parent / "system.txt"

with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

