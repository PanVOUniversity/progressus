"""Модуль с промптами для различных личностей.

Содержит системные промпты и описания стилей общения
для разных мотивирующих коучей.
"""

from .andrew_tate import SYSTEM_PROMPT as TATE_SYSTEM_PROMPT, PERSONALITY_DESCRIPTION as TATE_DESCRIPTION
from .grebenyuk import SYSTEM_PROMPT as GREBENYUK_SYSTEM_PROMPT, PERSONALITY_DESCRIPTION as GREBENYUK_DESCRIPTION
from .khabib import SYSTEM_PROMPT as KHABIB_SYSTEM_PROMPT, PERSONALITY_DESCRIPTION as KHABIB_DESCRIPTION
from .oleg_tinkov import SYSTEM_PROMPT as TINKOV_SYSTEM_PROMPT, PERSONALITY_DESCRIPTION as TINKOV_DESCRIPTION
from .tyler_durden import SYSTEM_PROMPT as DURDEN_SYSTEM_PROMPT, PERSONALITY_DESCRIPTION as DURDEN_DESCRIPTION

# Словарь с промптами для каждой личности
PERSONALITIES = {
    "andrew_tate": {
        "system_prompt": TATE_SYSTEM_PROMPT,
        "description": TATE_DESCRIPTION,
        "name": "Эндрю Тейт"
    },
    "grebenyuk": {
        "system_prompt": GREBENYUK_SYSTEM_PROMPT,
        "description": GREBENYUK_DESCRIPTION,
        "name": "Михаил Гребенюк"
    },
    "khabib": {
        "system_prompt": KHABIB_SYSTEM_PROMPT,
        "description": KHABIB_DESCRIPTION,
        "name": "Хабиб Нурмагомедов"
    },
    "oleg_tinkov": {
        "system_prompt": TINKOV_SYSTEM_PROMPT,
        "description": TINKOV_DESCRIPTION,
        "name": "Олег Тиньков"
    },
    "tyler_durden": {
        "system_prompt": DURDEN_SYSTEM_PROMPT,
        "description": DURDEN_DESCRIPTION,
        "name": "Тайлер Дёрден"
    }
}

def get_personality_prompt(personality_key: str) -> dict:
    """Получить промпт для указанной личности.
    
    Args:
        personality_key (str): Ключ личности (andrew_tate, grebenyuk, khabib, oleg_tinkov, tyler_durden)
        
    Returns:
        dict: Словарь с system_prompt, description и name
        
    Raises:
        KeyError: Если личность не найдена
    """
    if personality_key not in PERSONALITIES:
        # По умолчанию возвращаем Эндрю Тейт
        return PERSONALITIES["andrew_tate"]
    return PERSONALITIES[personality_key]
