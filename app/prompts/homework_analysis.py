"""Промпт для анализа домашних заданий.

Модуль содержит промпт для глубокого анализа выполнения заданий пользователем.
"""
import os
from pathlib import Path

# Загружаем промпт из текстового файла
PROMPT_FILE = Path(__file__).parent / "homework_analysis.txt"

with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    ANALYSIS_PROMPT_TEMPLATE = f.read()

