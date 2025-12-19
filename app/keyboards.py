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


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для вопроса о поле.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с вариантами:
            - Мужской
            - Женский
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мужской", callback_data="gender_male")],
        [InlineKeyboardButton(text="Женский", callback_data="gender_female")]
    ])


def get_values_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора 3 основных ценностей.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с ценностями:
            - Честность, Спокойствие, Дружба, семья
            - Деньги, Власть, Забота о других, Созидание
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Честность", callback_data="value_honesty")],
        [InlineKeyboardButton(text="Спокойствие", callback_data="value_peace")],
        [InlineKeyboardButton(text="Дружба, семья", callback_data="value_family")],
        [InlineKeyboardButton(text="Деньги", callback_data="value_money")],
        [InlineKeyboardButton(text="Власть", callback_data="value_power")],
        [InlineKeyboardButton(text="Забота о других", callback_data="value_care")],
        [InlineKeyboardButton(text="Созидание", callback_data="value_creation")],
        [InlineKeyboardButton(text="✅ Готово (выбрано 3)", callback_data="values_done")]
    ])


def get_development_spheres_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора сфер развития (можно выбрать несколько).
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с сферами:
            - Заработок, Отношения, Здоровье/Тело
            - Разум, Коммуникации
            - ✅ Готово
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Заработок", callback_data="sphere_earnings")],
        [InlineKeyboardButton(text="Отношения", callback_data="sphere_relationships")],
        [InlineKeyboardButton(text="Здоровье/Тело", callback_data="sphere_health")],
        [InlineKeyboardButton(text="Разум", callback_data="sphere_mind")],
        [InlineKeyboardButton(text="Коммуникации", callback_data="sphere_communication")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="spheres_done")]
    ])


def get_role_model_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора ролевой модели.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с ролевыми моделями:
            - Эндрю Тейт
            - Михаил Гребенюк
            - Хабиб
            - Олег Тиньков
            - Тайлер Дёрден
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Эндрю Тейт", callback_data="role_andrew_tate")],
        [InlineKeyboardButton(text="Михаил Гребенюк", callback_data="role_grebenyuk")],
        [InlineKeyboardButton(text="Хабиб", callback_data="role_khabib")],
        [InlineKeyboardButton(text="Олег Тиньков", callback_data="role_oleg_tinkov")],
        [InlineKeyboardButton(text="Тайлер Дёрден", callback_data="role_tyler_durden")]
    ])


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

