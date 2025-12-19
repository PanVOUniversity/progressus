"""Примеры кода для работы с моделью пользователя.

Модуль содержит примеры структур данных и функций для работы
с моделью пользователя и роадмапом.
"""

# Пример структуры для хранения модели пользователя
USER_MODEL_EXAMPLE = {
    "name": "имя",
    "archetype": {
        "motivation_type": "результат-ориентированный",
        "psycho_type": "амбициозный лидер",
        "ambition_level": "high",
        "action_style": "агрессивный"
    },
    "values": {
        "primary": "честность",
        "secondary": ["созидание", "деньги"],
        "deep_meaning": {
            "честность": "жить без масок",
            "созидание": "оставить след",
            "деньги": "независимость"
        }
    },
    "role_model": {
        "name": "Олег Тиньков",
        "admires": ["предпринимательство", "риск", "инновации"],
        "wants_to_adopt": "прямолинейность и действие"
    },
    "spheres": {
        "заработок": {"current_level": "ищет первый доход", "motivation": "независимость"},
        "разум": {"current_level": "хочет применять", "motivation": "экспертиза"},
        "коммуникации": {"current_level": "хочет влиять", "motivation": "лидерство"}
    },
    "communication": {
        "tone": "энергичный, вызывающий",
        "response_length": "развернутые",
        "works": ["челленджи", "метрики", "примеры лидеров"],
        "avoid": ["сложная теория", "мягкие советы"]
    },
    "strategy": {
        "main_goal": "стать успешным предпринимателем",
        "focus_sphere": "заработок",
        "synergy": "заработок → разум → коммуникации"
    }
}


def process_user_message(user_model, message):
    """Обработка сообщения пользователя с учетом его модели.
    
    Args:
        user_model: Словарь с моделью пользователя
        message: Сообщение от пользователя
    
    Returns:
        Персонализированный ответ
    """
    # Используй user_model для контекста
    tone = user_model["communication"]["tone"]
    spheres = user_model["spheres"]
    role_model = user_model["role_model"]
    
    # Генерируй ответ в соответствии с моделью
    response = generate_personalized_response(
        message, 
        tone=tone, 
        spheres=spheres,
        role_model=role_model
    )
    return response


def generate_personalized_response(message, tone, spheres, role_model):
    """Генерация персонализированного ответа.
    
    Args:
        message: Сообщение пользователя
        tone: Тон общения
        spheres: Сферы развития
        role_model: Ролевая модель
    
    Returns:
        Персонализированный ответ
    """
    # Здесь должна быть логика генерации ответа
    # с учетом всех параметров модели пользователя
    pass

