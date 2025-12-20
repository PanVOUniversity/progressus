"""Inline клавиатуры для бота.

Модуль содержит функции для создания inline клавиатур Telegram бота:
согласие на ПД, вопросы опросника, оплата, реферальные ссылки.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from app.config import settings


def get_privacy_consent_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для согласия на обработку персональных данных.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками:
            - "Согласен" - для принятия согласия
            - "Политика конфиденциальности" - ссылка на политику
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Согласен",
                callback_data="privacy_consent_accepted"
            )
        ],
        [
            InlineKeyboardButton(
                text="Политика конфиденциальности",
                url=settings.PRIVACY_POLICY_URL
            )
        ]
    ])


def get_gender_keyboard(selected_gender: str = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для вопроса о поле.
    
    Args:
        selected_gender: Выбранный пол ("Мужской" или "Женский")
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с вариантами:
            - Мужской
            - Женский
    """
    male_text = "✅ Мужской" if selected_gender == "Мужской" else "Мужской"
    female_text = "✅ Женский" if selected_gender == "Женский" else "Женский"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=male_text, callback_data="gender_male")],
        [InlineKeyboardButton(text=female_text, callback_data="gender_female")]
    ])


def get_values_keyboard(selected_values: list = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора 3 основных ценностей.
    
    Args:
        selected_values: Список выбранных ценностей
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с ценностями:
            - Честность, Спокойствие, Дружба, семья
            - Деньги, Власть, Забота о других, Созидание
    """
    if selected_values is None:
        selected_values = []
    
    value_map = {
        "Честность": "value_honesty",
        "Спокойствие": "value_peace",
        "Дружба, семья": "value_family",
        "Деньги": "value_money",
        "Власть": "value_power",
        "Забота о других": "value_care",
        "Созидание": "value_creation"
    }
    
    count = len(selected_values)
    done_text = f"✅ Готово (выбрано {count}/3)" if count > 0 else "✅ Готово (выбрано 0/3)"
    
    keyboard = []
    for value_name, callback_data in value_map.items():
        text = f"✅ {value_name}" if value_name in selected_values else value_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton(text=done_text, callback_data="values_done")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_development_spheres_keyboard(selected_spheres: list = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора сфер развития (можно выбрать несколько).
    
    Args:
        selected_spheres: Список выбранных сфер развития
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с сферами:
            - Заработок, Отношения, Здоровье/Тело
            - Разум, Коммуникации
            - ✅ Готово
    """
    if selected_spheres is None:
        selected_spheres = []
    
    sphere_map = {
        "Заработок": "sphere_earnings",
        "Отношения": "sphere_relationships",
        "Здоровье/Тело": "sphere_health",
        "Разум": "sphere_mind",
        "Коммуникации": "sphere_communication"
    }
    
    keyboard = []
    for sphere_name, callback_data in sphere_map.items():
        text = f"✅ {sphere_name}" if sphere_name in selected_spheres else sphere_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data="spheres_done")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_role_model_keyboard(selected_role: str = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора ролевой модели.
    
    Args:
        selected_role: Выбранная ролевая модель
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с ролевыми моделями:
            - Эндрю Тейт
            - Михаил Гребенюк
            - Хабиб
            - Олег Тиньков
            - Тайлер Дёрден
    """
    role_map = {
        "Эндрю Тейт": "role_andrew_tate",
        "Михаил Гребенюк": "role_grebenyuk",
        "Хабиб": "role_khabib",
        "Олег Тиньков": "role_oleg_tinkov",
        "Тайлер Дёрден": "role_tyler_durden"
    }
    
    keyboard = []
    for role_name, callback_data in role_map.items():
        text = f"✅ {role_name}" if selected_role == role_name else role_name
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_payment_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для оплаты premium доступа.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой оплаты.
    """
    from app.config import settings
    price_rub = settings.PREMIUM_PRICE // 100
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {price_rub} руб.", callback_data="payment_start")]
    ])


def get_share_referral_keyboard(referral_link: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для поделиться реферальной ссылкой.
    
    Args:
        referral_link (str): Реферальная ссылка пользователя
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой поделиться ссылкой:
            - "📤 Поделиться ссылкой" - открывает Telegram Share
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Поделиться ссылкой",
            url=f"https://t.me/share/url?url={referral_link}&text=Присоединяйся к Progressus!"
        )]
    ])


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает inline клавиатуру главного меню согласно дизайну.
    
    Кнопки меню отображаются под сообщением (inline), а не под клавиатурой.
    
    Returns:
        InlineKeyboardMarkup: Inline клавиатура главного меню с кнопками:
            - "Свободная консультация"
            - "Задания"
            - "Помощь"
            - "Оплата"
            - "Реферальная программа"
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Свободная консультация", callback_data="menu_consultation")],
        [InlineKeyboardButton(text="Задания", callback_data="menu_tasks")],
        [InlineKeyboardButton(text="Помощь", callback_data="menu_help")],
        [InlineKeyboardButton(text="Оплата", callback_data="menu_payment")],
        [InlineKeyboardButton(text="Реферальная программа", callback_data="menu_referral")]
    ])


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создает постоянную клавиатуру с основными кнопками.
    
    Returns:
        ReplyKeyboardMarkup: Постоянная клавиатура с кнопками:
            - "Меню" - возврат в главное меню
            - "🔄 Рестарт" - рестарт бота (с подтверждением)
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Меню"), KeyboardButton(text="🔄 Рестарт")]
        ],
        resize_keyboard=True,
        persistent=True
    )


def get_restart_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения рестарта.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками подтверждения:
            - "✅ Да, рестарт" - подтверждение рестарта
            - "❌ Отмена" - отмена рестарта
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, рестарт", callback_data="restart_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="restart_cancel")
        ]
    ])

