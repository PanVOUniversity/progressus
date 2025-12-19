Модули
======

Архитектура системы
-------------------

Progressusbot построен по модульной архитектуре с четким разделением ответственности:

* **Handlers** - обрабатывают команды и сообщения от пользователей Telegram
* **Services** - содержат бизнес-логику работы с пользователями и рефералами
* **Models** - определяют структуру данных в базе данных
* **GPT** - интеграция с OpenRouter API для анализа и генерации контента
* **Middleware** - промежуточное ПО для ограничения частоты запросов
* **Celery** - фоновые задачи для отправки уведомлений

Диаграмма архитектуры
~~~~~~~~~~~~~~~~~~~~~

.. mermaid::

   graph TB
       Telegram[Telegram API]:::telegram
       FastAPI[FastAPI<br/>app.main]:::fastapi
       Dispatcher[Dispatcher<br/>aiogram]:::dispatcher
       Handlers[Handlers<br/>start, survey, payments]:::handlers
       Services[Services<br/>user_service, referral_service]:::services
       GPT[GPT Module<br/>app.gpt]:::gpt
       Models[Models<br/>User, Survey, Report]:::models
       Database[(Database<br/>PostgreSQL)]:::database
       Redis[(Redis<br/>FSM Storage)]:::redis
       Celery[Celery Tasks<br/>notifications]:::celery
       
       Telegram --> FastAPI
       FastAPI --> Dispatcher
       Dispatcher --> Handlers
       Handlers --> Services
       Handlers --> GPT
       Handlers --> Models
       Services --> Models
       Models --> Database
       Dispatcher --> Redis
       Celery --> Database
       Celery --> Telegram
       
       classDef telegram fill:#e1f5ff,stroke:#01579b,stroke-width:2px
       classDef fastapi fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
       classDef dispatcher fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
       classDef handlers fill:#fff9c4,stroke:#f57f17,stroke-width:2px
       classDef services fill:#fff9c4,stroke:#f57f17,stroke-width:2px
       classDef gpt fill:#ffe0b2,stroke:#e65100,stroke-width:2px
       classDef models fill:#b2ebf2,stroke:#006064,stroke-width:2px
       classDef database fill:#e0e0e0,stroke:#424242,stroke-width:2px
       classDef redis fill:#e0e0e0,stroke:#424242,stroke-width:2px
       classDef celery fill:#f8bbd0,stroke:#880e4f,stroke-width:2px

Поток данных
~~~~~~~~~~~~

.. mermaid::

   graph LR
       User[Пользователь<br/>/start]:::user
       StartHandler[start.py<br/>cmd_start]:::handler
       UserService[user_service.py<br/>get_or_create_user]:::service
       PrivacyHandler[privacy.py<br/>privacy_consent_accepted]:::handler
       SurveyHandler[survey.py<br/>process_pain1-5]:::handler
       GPTModule[gpt.py<br/>analyze_survey]:::gpt
       PaymentHandler[payments.py<br/>start_payment]:::handler
       ReportHandler[reports.py<br/>process_report]:::handler
       GPTEval[gpt.py<br/>evaluate_report]:::gpt
       
       User --> StartHandler
       StartHandler --> UserService
       UserService --> PrivacyHandler
       PrivacyHandler --> SurveyHandler
       SurveyHandler --> GPTModule
       GPTModule --> PaymentHandler
       PaymentHandler --> ReportHandler
       ReportHandler --> GPTEval
       
       classDef user fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
       classDef handler fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
       classDef service fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
       classDef gpt fill:#fff9c4,stroke:#f57f17,stroke-width:2px

Содержание
----------

.. contents::
   :depth: 2
   :local:

Основные модули
---------------

Модуль ``app``
~~~~~~~~~~~~~~

Корневой модуль приложения, содержащий все основные компоненты системы.

**Ответственность:**
* Инициализация и настройка приложения
* Экспорт основных компонентов для использования в других модулях

**Связи:**
* Импортируется всеми модулями приложения
* Содержит пакеты: handlers, services, middleware

.. automodule:: app
   :members:
   :undoc-members:
   :show-inheritance:

Конфигурация
------------

Модуль ``app.config``
~~~~~~~~~~~~~~~~~~~~~~

Управляет всеми настройками приложения, загружая их из переменных окружения.

**Ответственность:**
* Хранение токенов и ключей API
* Настройки подключения к базам данных
* Параметры окружения (development/production)

**Используется:**
* Везде в приложении для доступа к настройкам через ``settings``
* При инициализации бота, БД, Redis, GPT клиента

**Связи:**
* Импортируется: ``app.main``, ``app.database``, ``app.gpt``, ``celery_app.celery_worker``
* Используется: всеми модулями для получения конфигурации

.. automodule:: app.config
   :members:
   :undoc-members:
   :show-inheritance:

База данных
-----------

Модуль ``app.database``
~~~~~~~~~~~~~~~~~~~~~~~~

Настраивает асинхронное подключение к PostgreSQL через SQLAlchemy и asyncpg.

**Ответственность:**
* Создание async engine для подключения к БД
* Фабрика сессий для работы с БД
* Базовый класс для всех моделей

**Используется:**
* Всеми модулями, работающими с БД (handlers, services)
* При создании таблиц при старте приложения

**Связи:**
* Импортируется: ``app.models``, ``app.handlers.*``, ``app.services.*``
* Использует: ``app.config.settings.DB_URL``

.. automodule:: app.database
   :members:
   :undoc-members:
   :show-inheritance:

Модели данных
-------------

Модуль ``app.models``
~~~~~~~~~~~~~~~~~~~~~~

Определяет структуру данных в базе данных через SQLAlchemy ORM.

**Модели:**

* **User** - информация о пользователе (уровень, категория, premium статус, рефералы)
* **Survey** - ответы пользователя на опросник и GPT анализ
* **Report** - отчеты пользователя о выполнении ДЗ с обратной связью от GPT
* **Payment** - записи о платежах за premium доступ

**Ответственность:**
* Определение схемы БД
* Связи между таблицами (relationships)
* Валидация данных на уровне БД

**Связи:**
* Используется: ``app.services.*`` для работы с данными
* Импортируется: ``app.handlers.*`` для создания записей
* Наследуется от: ``app.database.Base``

.. automodule:: app.models
   :members:
   :undoc-members:
   :show-inheritance:

FSM состояния
-------------

Модуль ``app.states``
~~~~~~~~~~~~~~~~~~~~~~

Определяет состояния конечного автомата для процесса прохождения опросника.

**Состояния:**
* ``privacy_consent`` - ожидание согласия на обработку ПД
* ``pain1`` - вопрос о главной боли
* ``pain2`` - вопрос о возрасте
* ``pain3`` - вопрос о предпочтениях
* ``pain4`` - вопрос о ролевых моделях
* ``pain5`` - вопрос о конкретных целях (текстовый ответ)
* ``finish`` - завершение опроса

**Ответственность:**
* Управление последовательностью вопросов опросника
* Хранение промежуточных ответов в Redis через FSM

**Связи:**
* Используется: ``app.handlers.start``, ``app.handlers.privacy``, ``app.handlers.survey``
* Хранится в: Redis через ``RedisStorage``

.. automodule:: app.states
   :members:
   :undoc-members:
   :show-inheritance:

GPT интеграция
--------------

Модуль ``app.gpt``
~~~~~~~~~~~~~~~~~~~

Интеграция с OpenRouter API для анализа ответов пользователей и генерации домашних заданий.

**Функции:**

* ``analyze_survey(answers)`` - анализирует ответы опросника, определяет категорию развития и генерирует ДЗ уровня 0
* ``evaluate_report(user_level, category, report_text, previous_homework)`` - оценивает отчет пользователя, повышает уровень и генерирует новое ДЗ

**Ответственность:**
* Коммуникация с GPT через OpenRouter API
* Парсинг ответов GPT и извлечение структурированных данных
* Генерация персонализированного контента

**Связи:**
* Используется: ``app.handlers.survey`` (для анализа опросника), ``app.handlers.reports`` (для оценки отчетов)
* Использует: ``app.config.settings.OPENROUTER_API_KEY``, ``OPENROUTER_MODEL``

.. automodule:: app.gpt
   :members:
   :undoc-members:
   :show-inheritance:

Клавиатуры
----------

Модуль ``app.keyboards``
~~~~~~~~~~~~~~~~~~~~~~~~~

Создает inline клавиатуры для взаимодействия с пользователем в Telegram.

**Функции:**

* ``get_privacy_consent_keyboard()`` - клавиатура для согласия на ПД
* ``get_pain1_keyboard()`` - варианты ответа на вопрос 1 (главная боль)
* ``get_pain2_keyboard()`` - варианты ответа на вопрос 2 (возраст)
* ``get_pain3_keyboard()`` - варианты ответа на вопрос 3 (предпочтения)
* ``get_pain4_keyboard()`` - варианты ответа на вопрос 4 (ролевые модели)
* ``get_payment_keyboard()`` - кнопка оплаты premium
* ``get_share_referral_keyboard(referral_link)`` - кнопка поделиться реферальной ссылкой

**Ответственность:**
* Создание UI элементов для взаимодействия
* Обработка callback данных для идентификации выбранных вариантов

**Связи:**
* Используется: всеми обработчиками для отображения клавиатур
* Импортируется: ``app.handlers.*``

.. automodule:: app.keyboards
   :members:
   :undoc-members:
   :show-inheritance:

Основное приложение
-------------------

Модуль ``app.main``
~~~~~~~~~~~~~~~~~~~~

Точка входа приложения. Создает FastAPI сервер и управляет жизненным циклом бота.

**Компоненты:**

* ``bot`` - экземпляр Telegram бота
* ``dp`` - диспетчер aiogram для обработки обновлений
* ``app`` - FastAPI приложение
* ``lifespan()`` - управление жизненным циклом (создание таблиц, webhook/polling)

**Ответственность:**
* Инициализация всех компонентов системы
* Регистрация роутеров и middleware
* Обработка webhook запросов от Telegram
* Управление запуском и остановкой бота

**Связи:**
* Импортирует: все handlers, ``app.database``, ``app.config``
* Регистрирует: все роутеры из handlers
* Использует: ``app.middleware.rate_limit.RateLimitMiddleware``

.. automodule:: app.main
   :members:
   :undoc-members:
   :show-inheritance:

Обработчики команд
------------------

Обработчики команд и сообщений от пользователей Telegram. Каждый обработчик отвечает за определенную функциональность.

Обработчик /start
~~~~~~~~~~~~~~~~~~

Модуль ``app.handlers.start``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Обрабатывает команду ``/start`` и инициализирует взаимодействие с пользователем.

**Функции:**

* ``cmd_start()`` - обработка команды ``/start`` без реферальной ссылки
* ``cmd_start_with_ref()`` - обработка команды ``/start ref{user_id}`` с реферальной ссылкой

**Ответственность:**
* Создание или получение пользователя из БД
* Обработка реферальных ссылок
* Проверка согласия на обработку ПД
* Запуск опросника или переход к нему

**Связи:**
* Использует: ``app.services.user_service.get_or_create_user()``
* Использует: ``app.services.referral_service.process_referral()``
* Использует: ``app.states.SurveyStates`` для управления состоянием
* Использует: ``app.keyboards.get_privacy_consent_keyboard()``, ``get_pain1_keyboard()``

**Поток выполнения:**

1. Пользователь отправляет ``/start``
2. Получаем или создаем пользователя через ``user_service``
3. Если есть реферальная ссылка - обрабатываем через ``referral_service``
4. Проверяем согласие на ПД:
   * Если нет - показываем клавиатуру согласия
   * Если есть - переходим к первому вопросу опросника

.. automodule:: app.handlers.start
   :members:
   :undoc-members:
   :show-inheritance:

Обработчик согласия на ПД
~~~~~~~~~~~~~~~~~~~~~~~~~~

Модуль ``app.handlers.privacy``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Обрабатывает согласие пользователя на обработку персональных данных.

**Функции:**

* ``privacy_consent_accepted()`` - обработка нажатия кнопки "Согласен"

**Ответственность:**
* Сохранение согласия в БД с датой и временем
* Переход к опроснику после получения согласия

**Связи:**
* Использует: ``app.models.User`` для обновления записи
* Использует: ``app.states.SurveyStates.pain1`` для перехода к опроснику
* Использует: ``app.keyboards.get_pain1_keyboard()``

.. automodule:: app.handlers.privacy
   :members:
   :undoc-members:
   :show-inheritance:

Обработчик опросника
~~~~~~~~~~~~~~~~~~~~

Модуль ``app.handlers.survey``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Обрабатывает прохождение опросника из 5 вопросов через FSM.

**Функции:**

* ``process_pain1()`` - обработка ответа на вопрос 1 (главная боль)
* ``process_pain2()`` - обработка ответа на вопрос 2 (возраст)
* ``process_pain3()`` - обработка ответа на вопрос 3 (предпочтения)
* ``process_pain4()`` - обработка ответа на вопрос 4 (ролевые модели)
* ``process_pain5()`` - обработка текстового ответа на вопрос 5 (конкретные цели)

**Ответственность:**
* Сохранение ответов в FSM state
* Переход между состояниями опросника
* Отправка всех ответов в GPT для анализа
* Сохранение результатов анализа в БД
* Обновление категории и ДЗ пользователя

**Связи:**
* Использует: ``app.states.SurveyStates`` для управления состоянием
* Использует: ``app.gpt.analyze_survey()`` для анализа ответов
* Использует: ``app.models.Survey`` для сохранения опроса
* Использует: ``app.services.user_service.update_user_category()``, ``update_user_homework()``
* Использует: ``app.keyboards.*`` для отображения вариантов ответов

**Поток выполнения:**

1. Пользователь выбирает вариант ответа на вопрос 1-4 → сохраняется в FSM state → переход к следующему вопросу
2. Пользователь вводит текстовый ответ на вопрос 5 → сохраняется в FSM state
3. Собираются все ответы из FSM state
4. Отправка в GPT через ``analyze_survey()``
5. Получение категории, анализа и ДЗ уровня 0
6. Сохранение опроса в БД
7. Обновление категории и ДЗ пользователя
8. Показ результатов и предложение оплаты premium

.. automodule:: app.handlers.survey
   :members:
   :undoc-members:
   :show-inheritance:

Обработчик платежей
~~~~~~~~~~~~~~~~~~~

Модуль ``app.handlers.payments``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Обрабатывает оплату premium доступа (в текущей версии - заглушка).

**Функции:**

* ``start_payment()`` - обработка начала процесса оплаты (заглушка)

**Ответственность:**
* Активация premium доступа без реального платежа (заглушка)
* Создание записи о платеже в БД
* Повышение уровня пользователя до 1
* Обработка реферальной системы при оплате

**Связи:**
* Использует: ``app.models.Payment`` для создания записи о платеже
* Использует: ``app.models.User`` для активации premium и повышения уровня
* Использует: ``app.services.referral_service.add_referral_on_payment()``
* Использует: ``app.services.user_service.update_user_level()``

**Примечание:** Реальный код обработки платежей закомментирован и может быть активирован после настройки ``PROVIDER_TOKEN``.

.. automodule:: app.handlers.payments
   :members:
   :undoc-members:
   :show-inheritance:

Обработчик отчетов
~~~~~~~~~~~~~~~~~~~

Модуль ``app.handlers.reports``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Обрабатывает отправку отчетов пользователями о выполнении домашних заданий.

**Функции:**

* ``cmd_report()`` - обработка команды ``/report`` (запрос текста отчета)
* ``process_report()`` - обработка текста отчета пользователя

**Ответственность:**
* Проверка наличия premium доступа и активного ДЗ
* Отправка отчета в GPT для оценки
* Сохранение отчета в БД
* Обновление уровня пользователя на основе оценки GPT
* Генерация нового ДЗ для нового уровня

**Связи:**
* Использует: ``app.models.User`` для проверки premium и получения текущего ДЗ
* Использует: ``app.models.Report`` для сохранения отчета
* Использует: ``app.gpt.evaluate_report()`` для оценки отчета
* Использует: ``app.services.user_service.update_user_level()``, ``update_user_homework()``

**Поток выполнения:**

1. Пользователь отправляет ``/report`` → запрос текста отчета
2. Пользователь отправляет текст отчета
3. Проверка premium доступа и активного ДЗ
4. Отправка отчета в GPT через ``evaluate_report()``
5. Получение обратной связи, нового уровня и нового ДЗ
6. Сохранение отчета в БД
7. Обновление уровня и ДЗ пользователя
8. Показ результатов пользователю

.. automodule:: app.handlers.reports
   :members:
   :undoc-members:
   :show-inheritance:

Обработчик реферальной системы
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Модуль ``app.handlers.referral``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Обрабатывает команду ``/ref`` для получения реферальной ссылки и статистики.

**Функции:**

* ``cmd_referral()`` - обработка команд ``/ref`` и ``/referral``

**Ответственность:**
* Генерация реферальной ссылки для пользователя
* Получение статистики по рефералам
* Отображение ссылки и статистики с кнопкой поделиться

**Связи:**
* Использует: ``app.services.referral_service.generate_referral_link()``
* Использует: ``app.services.referral_service.get_referral_stats()``
* Использует: ``app.keyboards.get_share_referral_keyboard()``

.. automodule:: app.handlers.referral
   :members:
   :undoc-members:
   :show-inheritance:

Сервисы
-------

Сервисы содержат бизнес-логику работы с данными пользователей.

Сервис пользователей
~~~~~~~~~~~~~~~~~~~~~

Модуль ``app.services.user_service``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Сервис для работы с пользователями в базе данных.

**Функции:**

* ``get_or_create_user(session, user_id, username)`` - получает пользователя из БД или создает нового
* ``update_user_level(session, user_id, new_level)`` - обновляет уровень пользователя (максимум 10)
* ``update_user_category(session, user_id, category)`` - обновляет категорию развития пользователя
* ``update_user_homework(session, user_id, homework)`` - обновляет текущее домашнее задание пользователя

**Ответственность:**
* CRUD операции с пользователями
* Валидация данных (например, ограничение уровня максимумом 10)
* Управление транзакциями БД

**Связи:**
* Используется: ``app.handlers.start``, ``app.handlers.survey``, ``app.handlers.reports``, ``app.handlers.payments``
* Использует: ``app.models.User`` для работы с данными
* Использует: ``app.database.AsyncSession`` для работы с БД

.. automodule:: app.services.user_service
   :members:
   :undoc-members:
   :show-inheritance:

Сервис реферальной системы
~~~~~~~~~~~~~~~~~~~~~~~~~~

Модуль ``app.services.referral_service``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Сервис для работы с реферальной системой.

**Функции:**

* ``generate_referral_link(user_id, bot_username)`` - генерирует реферальную ссылку формата ``https://t.me/{bot_username}?start=ref{user_id}``
* ``process_referral(session, user_id, referrer_id)`` - обрабатывает реферала при регистрации, устанавливает связь между пользователем и реферером
* ``add_referral_on_payment(session, user_id)`` - добавляет реферала в список реферера при оплате premium, возвращает referrer_id если нужно повысить уровень (3+ реферала)
* ``get_referral_stats(session, user_id)`` - получает статистику рефералов (общее количество, оплатившие, сколько осталось до повышения уровня)

**Ответственность:**
* Управление реферальными связями
* Подсчет статистики рефералов
* Логика повышения уровня реферера за рефералов

**Связи:**
* Используется: ``app.handlers.start`` (для обработки реферальных ссылок), ``app.handlers.payments`` (для добавления реферала при оплате), ``app.handlers.referral`` (для статистики)
* Использует: ``app.models.User`` для работы с данными
* Использует: ``app.config.settings.BOT_USERNAME`` для генерации ссылок

**Логика реферальной системы:**

1. При регистрации через реферальную ссылку устанавливается ``referrer_id``
2. При оплате premium реферал добавляется в список ``referrals`` реферера
3. Если у реферера набирается 3+ оплативших реферала, его уровень повышается на 1

.. automodule:: app.services.referral_service
   :members:
   :undoc-members:
   :show-inheritance:

Middleware
----------

Rate Limiting Middleware
~~~~~~~~~~~~~~~~~~~~~~~~~

Модуль ``app.middleware.rate_limit``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Middleware для ограничения частоты запросов от пользователей (30 запросов в минуту).

**Класс:**

* ``RateLimitMiddleware`` - middleware для rate limiting

**Ответственность:**
* Защита от спама и злоупотреблений
* Отслеживание количества запросов от каждого пользователя
* Блокировка запросов сверх лимита

**Механизм работы:**

1. Извлекает ``user_id`` из события (Message, CallbackQuery)
2. Проверяет количество запросов пользователя в текущем временном окне (1 минута)
3. Если лимит превышен (30 запросов) - блокирует обработку запроса
4. Очищает старые запросы вне временного окна

**Связи:**
* Регистрируется в: ``app.main`` для всех сообщений и callback queries
* Используется: автоматически для всех входящих запросов через диспетчер

.. automodule:: app.middleware.rate_limit
   :members:
   :undoc-members:
   :show-inheritance:

Celery задачи
-------------

Конфигурация Celery
~~~~~~~~~~~~~~~~~~~~

Модуль ``celery_app.celery_worker``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Настройка и создание экземпляра Celery приложения для фоновых задач.

**Компоненты:**

* ``celery_app`` - экземпляр Celery приложения

**Ответственность:**
* Конфигурация Celery (broker, backend, сериализация)
* Настройка лимитов времени выполнения задач
* Регистрация задач из модуля ``celery_app.tasks``

**Связи:**
* Использует: ``app.config.settings.REDIS_URL`` для broker и backend
* Используется: ``celery_app.tasks`` для регистрации задач

.. automodule:: celery_app.celery_worker
   :members:
   :undoc-members:
   :show-inheritance:

Фоновые задачи
~~~~~~~~~~~~~~~

Модуль ``celery_app.tasks``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Фоновые задачи Celery для отправки уведомлений пользователям.

**Задачи:**

* ``send_daily_homework(user_id)`` - отправляет ежедневное домашнее задание пользователю
* ``send_reminder(user_id)`` - отправляет напоминание об отчете если не было отчета за 2 дня
* ``schedule_daily_tasks()`` - планирует ежедневные задачи для всех premium пользователей (не реализована)

**Ответственность:**
* Асинхронная отправка уведомлений через Telegram бота
* Проверка условий перед отправкой (premium доступ, наличие ДЗ, дата последнего отчета)
* Обработка ошибок при отправке

**Связи:**
* Использует: ``celery_app.celery_worker.celery_app`` для регистрации задач
* Использует: ``app.models.User`` для получения данных пользователя
* Использует: ``app.config.settings.BOT_TOKEN`` для создания бота
* Использует: ``app.database.async_session_maker`` для работы с БД

**Примечание:** Задача ``schedule_daily_tasks()`` должна запускаться по расписанию (например, через cron) и вызывать ``send_daily_homework()`` для всех premium пользователей.

.. automodule:: celery_app.tasks
   :members:
   :undoc-members:
   :show-inheritance:
