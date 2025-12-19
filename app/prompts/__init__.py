"""Модуль с промптами для GPT.

Содержит промпты для различных личностей коучей и системные промпты.
"""

from .personalities import PERSONALITIES, get_personality_prompt

__all__ = [
    "PERSONALITIES",
    "get_personality_prompt"
]
