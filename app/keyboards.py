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


def get_values_keyboard(selected_values: list[str] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора 3 основных ценностей.
    
    Args:
        selected_values: Список выбранных ценностей (например, ["Честность", "Спокойствие"])
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с ценностями:
            - Честность, Спокойствие, Дружба, семья
            - Деньги, Власть, Забота о других, Созидание
    """
    if selected_values is None:
        selected_values = []
    
    # Маппинг значений на callback_data и текст
    value_buttons = [
        ("Честность", "value_honesty"),
        ("Спокойствие", "value_peace"),
        ("Дружба, семья", "value_family"),
        ("Деньги", "value_money"),
        ("Власть", "value_power"),
        ("Забота о других", "value_care"),
        ("Созидание", "value_creation"),
    ]
    
    # Создаем кнопки с галочками для выбранных значений
    keyboard = []
    for value_text, callback_data in value_buttons:
        if value_text in selected_values:
            button_text = f"✅ {value_text}"
        else:
            button_text = value_text
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    # Кнопка "Готово" с количеством выбранных
    count = len(selected_values)
    done_text = f"✅ Готово (выбрано {count})"
    keyboard.append([InlineKeyboardButton(text=done_text, callback_data="values_done")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_development_spheres_keyboard(selected_spheres: list[str] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора сфер развития (можно выбрать несколько).
    
    Args:
        selected_spheres: Список выбранных сфер (например, ["Заработок", "Отношения"])
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с сферами:
            - Заработок, Отношения, Здоровье/Тело
            - Разум, Коммуникации
            - ✅ Готово
    """
    if selected_spheres is None:
        selected_spheres = []
    
    # Маппинг сфер на callback_data и текст
    sphere_buttons = [
        ("Заработок", "sphere_earnings"),
        ("Отношения", "sphere_relationships"),
        ("Здоровье/Тело", "sphere_health"),
        ("Разум", "sphere_mind"),
        ("Коммуникации", "sphere_communication"),
    ]
    
    # Создаем кнопки с галочками для выбранных сфер
    keyboard = []
    for sphere_text, callback_data in sphere_buttons:
        if sphere_text in selected_spheres:
            button_text = f"✅ {sphere_text}"
        else:
            button_text = sphere_text
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
    
    # Кнопка "Готово"
    keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data="spheres_done")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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


def get_payment_keyboard(has_premium: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру для оплаты premium доступа.
    
    Args:
        has_premium (bool): Если True, показывает кнопку отключения подписки
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой оплаты или отключения подписки.
    """
    from app.config import settings
    price_rub = settings.PREMIUM_PRICE // 100
    
    if has_premium:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отключить подписку", callback_data="subscription_cancel")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {price_rub} руб.", callback_data="payment_start")],
            [InlineKeyboardButton(text="🎟️ Ввести промокод", callback_data="promo_code_enter")]
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
            - "Персонализация"
            - "Помощь"
            - "Оплата"
            - "Реферальная программа"
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Свободная консультация", callback_data="menu_consultation")],
        [InlineKeyboardButton(text="Задания", callback_data="menu_tasks")],
        [InlineKeyboardButton(text="Персонализация", callback_data="menu_personalization")],
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


def get_subscription_cancel_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения отключения подписки.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками подтверждения:
            - "✅ Да, отключить" - подтверждение отключения
            - "❌ Отмена" - отмена отключения
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отключить", callback_data="subscription_cancel_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="subscription_cancel_cancel")
        ]
    ])

