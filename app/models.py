"""SQLAlchemy модели для БД.

Модуль содержит все модели данных для работы с базой данных:
User, Survey, Report, Payment.
"""
from sqlalchemy import Column, BigInteger, Boolean, Integer, String, Text, Date, DateTime, JSON, ARRAY, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """Модель пользователя Telegram бота.
    
    Хранит информацию о пользователе: его уровень, категорию развития,
    статус premium, реферальную информацию и домашние задания.
    
    Attributes:
        user_id (int): Telegram ID пользователя (первичный ключ)
        username (Optional[str]): Username пользователя в Telegram
        privacy_consent_accepted (bool): Флаг согласия на обработку ПД
        privacy_consent_date (Optional[datetime]): Дата получения согласия
        is_premium (bool): Флаг наличия premium доступа
        level (int): Уровень пользователя от 0 до 10
        category (Optional[str]): Категория развития (finances/health/mental)
        category_progress (dict): JSON с прогрессом по категории
        referrals (List[int]): Список ID рефералов пользователя
        referrer_id (Optional[int]): ID реферера пользователя
        last_report (Optional[date]): Дата последнего отчета
        current_homework (Optional[str]): Текущее домашнее задание
        created_at (datetime): Дата создания записи
        updated_at (datetime): Дата последнего обновления
        surveys (List[Survey]): Список опросов пользователя
        reports (List[Report]): Список отчетов пользователя
        payments (List[Payment]): Список платежей пользователя
    """
    __tablename__ = "users"
    
    user_id = Column(BigInteger, primary_key=True, index=True)
    """Telegram ID пользователя (первичный ключ)."""
    
    username = Column(String(255), nullable=True)
    """Username пользователя в Telegram."""
    
    # Согласие на обработку ПД
    privacy_consent_accepted = Column(Boolean, default=False, nullable=False)
    """Флаг согласия на обработку персональных данных."""
    
    privacy_consent_date = Column(DateTime(timezone=True), nullable=True)
    """Дата получения согласия на обработку ПД."""
    
    # Premium и уровни
    is_premium = Column(Boolean, default=False, nullable=False)
    """Флаг наличия premium доступа."""
    
    premium_expires_at = Column(DateTime(timezone=True), nullable=True)
    """Дата окончания premium доступа. Если None, премиум не активен."""
    
    level = Column(Integer, default=0, nullable=False)  # 0-10
    """Уровень пользователя от 0 до 10."""
    
    # Категория и прогресс
    category = Column(String(50), nullable=True)  # finances/health/mental
    """Категория развития: finances, health или mental."""
    
    category_progress = Column(JSON, nullable=True, default=dict)
    """JSON с прогрессом по категории развития."""
    
    # Личность коуча
    personality = Column(String(50), nullable=True)  # andrew_tate/grebenyuk/khabib/oleg_tinkov/tyler_durden
    """Выбранная личность коуча: andrew_tate, grebenyuk, khabib, oleg_tinkov или tyler_durden."""
    
    # Персональная информация из опросника
    name = Column(String(255), nullable=True)
    """Имя пользователя."""
    
    gender = Column(String(20), nullable=True)  # Мужской/Женский
    """Пол пользователя."""
    
    age = Column(Integer, nullable=True)
    """Возраст пользователя."""
    
    values = Column(ARRAY(String), nullable=True)  # Список из 3 ценностей
    """Три основные ценности пользователя."""
    
    development_spheres = Column(ARRAY(String), nullable=True)  # Заработок, Отношения, Здоровье/Тело, Разум, Коммуникации
    """Сферы развития, выбранные пользователем."""
    
    # Роадмап достижения цели
    goal_3months = Column(Text, nullable=True)
    """Цель пользователя на ближайшие 3 месяца."""
    
    roadmap = Column(JSON, nullable=True)
    """Роадмап достижения цели с milestone (недели 1-2, 3-4, 5-8, 9-12)."""
    
    # Реферальная система
    referrals = Column(ARRAY(BigInteger), nullable=True, default=list)
    """Список ID рефералов пользователя."""
    
    referrer_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    """ID реферера пользователя."""
    
    # Домашние задания и отчеты
    last_report = Column(Date, nullable=True)
    """Дата последнего отчета по домашнему заданию."""
    
    current_homework = Column(Text, nullable=True)
    """Текущее домашнее задание пользователя."""
    
    homework_needs_revision = Column(Boolean, default=False, nullable=False)
    """Флаг того, что текущее ДЗ требует правок (пользователь выполнил плохо)."""
    
    # Сохранение состояния опроса для восстановления после перезапуска
    survey_state = Column(JSON, nullable=True)
    """JSON с текущим состоянием опроса и данными FSM для восстановления после перезапуска."""
    
    # Использование консультации
    consultation_used = Column(Boolean, default=False, nullable=False)
    """Флаг использования бесплатной консультации (доступна только один раз без премиума)."""
    
    # Персонализация - глубокие вопросы для лучшего понимания пользователя
    personalization_data = Column(JSON, nullable=True)
    """JSON с данными персонализации: вопросы и ответы для глубокого понимания пользователя."""
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    """Дата создания записи."""
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    """Дата последнего обновления записи."""
    
    # Relationships
    surveys = relationship("Survey", back_populates="user", cascade="all, delete-orphan")
    """Связь с опросами пользователя."""
    
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")
    """Связь с отчетами пользователя."""
    
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    """Связь с платежами пользователя."""


class Survey(Base):
    """Модель опроса пользователя.
    
    Хранит ответы пользователя на опросник:
    - 5 базовых вопросов (пол, возраст, имя, ценности, сферы)
    - 5 развернутых вопросов от GPT
    - Ролевая модель
    - Цель на 3 месяца
    - Роадмап достижения цели
    
    Attributes:
        id (int): Уникальный идентификатор опроса (первичный ключ)
        user_id (int): ID пользователя, прошедшего опрос
        basic_answers (dict): JSON с ответами на 5 базовых вопросов
        detailed_answers (dict): JSON с ответами на 5 развернутых вопросов от GPT
        role_model (str): Выбранная ролевая модель
        goal_3months (str): Цель на 3 месяца
        roadmap (dict): JSON с роадмапом достижения цели
        gpt_analysis (Optional[str]): Текст анализа ответов от GPT
        created_at (datetime): Дата создания опроса
        user (User): Связь с пользователем
    """
    __tablename__ = "surveys"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    """Уникальный идентификатор опроса."""
    
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    """ID пользователя, прошедшего опрос."""
    
    # Базовые ответы (5 вопросов: пол, возраст, имя, ценности, сферы)
    basic_answers = Column(JSON, nullable=False)
    """JSON с ответами на 5 базовых вопросов опросника."""
    
    # Развернутые ответы (5 вопросов от GPT)
    detailed_answers = Column(JSON, nullable=True)
    """JSON с ответами на 5 развернутых вопросов, сгенерированных GPT."""
    
    # Развернутые вопросы от GPT
    detailed_questions = Column(JSON, nullable=True)
    """JSON с 5 развернутыми вопросами, сгенерированными GPT."""
    
    # Ролевая модель
    role_model = Column(String(50), nullable=True)
    """Выбранная ролевая модель: andrew_tate, grebenyuk, khabib, oleg_tinkov, tyler_durden."""
    
    # Цель на 3 месяца
    goal_3months = Column(Text, nullable=True)
    """Цель пользователя на ближайшие 3 месяца."""
    
    # Роадмап
    roadmap = Column(JSON, nullable=True)
    """JSON с роадмапом достижения цели (недели 1-2, 3-4, 5-8, 9-12)."""
    
    # GPT анализ
    gpt_analysis = Column(Text, nullable=True)
    """Текст анализа ответов от GPT."""
    
    # Временная метка
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    """Дата создания опроса."""
    
    # Relationship
    user = relationship("User", back_populates="surveys")
    """Связь с пользователем."""


class Report(Base):
    """Модель отчета пользователя по домашнему заданию.
    
    Хранит отчет пользователя о выполнении ДЗ, обратную связь от GPT
    и изменение уровня пользователя после оценки отчета.
    
    Attributes:
        id (int): Уникальный идентификатор отчета (первичный ключ)
        user_id (int): ID пользователя, отправившего отчет
        report_text (str): Текст отчета пользователя
        gpt_feedback (Optional[str]): Обратная связь от GPT по отчету
        level_before (int): Уровень пользователя до оценки отчета
        level_after (int): Уровень пользователя после оценки отчета
        created_at (datetime): Дата создания отчета
        user (User): Связь с пользователем
    """
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    """Уникальный идентификатор отчета."""
    
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    """ID пользователя, отправившего отчет."""
    
    # Текст отчета
    report_text = Column(Text, nullable=False)
    """Текст отчета пользователя о выполнении ДЗ."""
    
    # GPT обратная связь
    gpt_feedback = Column(Text, nullable=True)
    """Обратная связь от GPT по отчету."""
    
    # Уровни до и после
    level_before = Column(Integer, nullable=False)
    """Уровень пользователя до оценки отчета."""
    
    level_after = Column(Integer, nullable=False)
    """Уровень пользователя после оценки отчета."""
    
    # Статус выполнения ДЗ
    is_approved = Column(Boolean, nullable=True)
    """True если ДЗ выполнено хорошо, False если требует правок, None если еще не оценено."""
    
    # Правки к ДЗ (если требуется)
    revision_required = Column(Boolean, default=False, nullable=False)
    """Флаг того, что требуется переделать ДЗ с правками."""
    
    # Временная метка
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    """Дата создания отчета."""
    
    # Relationship
    user = relationship("User", back_populates="reports")
    """Связь с пользователем."""


class Payment(Base):
    """Модель платежа пользователя.
    
    Хранит информацию о платежах пользователя за premium доступ.
    
    Attributes:
        id (int): Уникальный идентификатор платежа (первичный ключ)
        user_id (int): ID пользователя, совершившего платеж
        payment_id (str): Уникальный ID платежа от Telegram (уникальный индекс)
        amount (int): Сумма платежа в копейках
        status (str): Статус платежа (completed, pending и т.д.)
        created_at (datetime): Дата создания платежа
        user (User): Связь с пользователем
    """
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    """Уникальный идентификатор платежа."""
    
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    """ID пользователя, совершившего платеж."""
    
    # Telegram payment ID
    payment_id = Column(String(255), unique=True, nullable=False, index=True)
    """Уникальный ID платежа от Telegram."""
    
    # Сумма в копейках
    amount = Column(Integer, nullable=False)
    """Сумма платежа в копейках."""
    
    # Статус
    status = Column(String(50), nullable=False)
    """Статус платежа (completed, pending и т.д.)."""
    
    # Временная метка
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    """Дата создания платежа."""
    
    # Relationship
    user = relationship("User", back_populates="payments")
    """Связь с пользователем."""

