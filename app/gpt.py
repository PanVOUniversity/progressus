"""OpenRouter API клиент для анализа опросов и генерации ДЗ.

Модуль предоставляет функции для работы с GPT через OpenRouter API:
анализ ответов опросника, генерация развернутых вопросов, роадмапа и оценка отчетов пользователей.
"""
from openai import AsyncOpenAI
from app.config import settings
from app.prompts import get_personality_prompt
from app.prompts.system import SYSTEM_PROMPT
from typing import List, Dict

# OpenRouter использует OpenAI-совместимый API
client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://progressusbot.com",  # Опционально для OpenRouter
        "X-Title": "Progressusbot"
    }
)
"""Асинхронный клиент OpenAI для работы с OpenRouter API."""


def clean_markdown(text: str) -> str:
    """Удаляет markdown форматирование и звездочки из текста.
    
    Args:
        text (str): Текст с возможным markdown форматированием
        
    Returns:
        str: Очищенный текст без звездочек и markdown
    """
    if not text:
        return text
    
    # Убираем звездочки и markdown
    text = text.replace('**', '').replace('*', '').replace('__', '').replace('_', '')
    text = text.replace('`', '').replace('```', '').replace('#', '').replace('##', '')
    # Убираем лишние пробелы
    text = ' '.join(text.split())
    
    return text.strip()


def _map_role_model_to_personality(role_model: str) -> str:
    """Маппинг ролевой модели в ключ личности.
    
    Args:
        role_model (str): Выбранная ролевая модель
        
    Returns:
        str: Ключ личности (andrew_tate, grebenyuk, khabib, oleg_tinkov, tyler_durden)
    """
    mapping = {
        "Эндрю Тейт": "andrew_tate",
        "Михаил Гребенюк": "grebenyuk",
        "Гребенюк": "grebenyuk",
        "Хабиб": "khabib",
        "Хабиб Нурмагомедов": "khabib",
        "Олег Тиньков": "oleg_tinkov",
        "Тиньков": "oleg_tinkov",
        "Тайлер Дёрден": "tyler_durden",
        "Тайлер": "tyler_durden",
        "andrew_tate": "andrew_tate",
        "grebenyuk": "grebenyuk",
        "khabib": "khabib",
        "oleg_tinkov": "oleg_tinkov",
        "tyler_durden": "tyler_durden"
    }
    return mapping.get(role_model, "andrew_tate")  # По умолчанию


async def generate_detailed_questions(basic_answers: Dict) -> List[Dict[str, str]]:
    """Генерирует по 2 вопроса для каждой выбранной сферы развития.
    
    На основе ответов на базовые вопросы (пол, возраст, имя, ценности, сферы)
    генерирует по 2 персонализированных вопроса для каждой выбранной сферы развития.
    Каждый вопрос отправляется отдельным сообщением.
    
    Args:
        basic_answers (Dict): Словарь с базовыми ответами:
            - gender: Мужской/Женский
            - age: возраст (int)
            - name: имя (str)
            - values: список из 3 ценностей
            - development_spheres: список сфер развития
        
    Returns:
        List[Dict[str, str]]: Список словарей с вопросами:
            - Каждый словарь содержит: {"sphere": str, "question": str}
            - Для каждой сферы генерируется 2 вопроса
        
    Example:
        .. code-block:: python
        
            basic_answers = {
                "gender": "Мужской",
                "age": 25,
                "name": "Иван",
                "values": ["Деньги", "Власть", "Созидание"],
                "development_spheres": ["Заработок", "Разум"]
            }
            questions = await generate_detailed_questions(basic_answers)
            # Вернет список вида:
            # [
            #     {"sphere": "Заработок", "question": "Сколько ты зарабатываешь в месяц?"},
            #     {"sphere": "Заработок", "question": "В какой нише ты зарабатываешь или пытаешься зарабатывать?"},
            #     {"sphere": "Разум", "question": "..."},
            #     {"sphere": "Разум", "question": "..."}
            # ]
    """
    development_spheres = basic_answers.get('development_spheres', [])
    
    if not development_spheres:
        return []
    
    all_questions = []
    
    # Генерируем по 2 вопроса для каждой сферы
    for sphere in development_spheres:
        prompt = f"""На основе ответов пользователя на базовые вопросы, сгенерируй 2 коротких, конкретных вопроса для сферы "{sphere}".

Базовые ответы пользователя:
- Пол: {basic_answers.get('gender', 'не указано')}
- Возраст: {basic_answers.get('age', 'не указано')}
- Имя: {basic_answers.get('name', 'не указано')}
- Ценности: {', '.join(basic_answers.get('values', []))}
- Сфера развития: {sphere}

Сгенерируй 2 коротких вопроса для сферы "{sphere}", которые помогут понять:
1. Текущую ситуацию пользователя в этой сфере (что уже есть, что достигнуто)
2. Конкретные планы, намерения или барьеры в этой сфере

ВАЖНО:
- Каждый вопрос должен быть КОРОТКИМ (одно предложение, максимум 15-20 слов)
- Вопросы должны быть конкретными и понятными
- Первый вопрос должен выяснить текущую ситуацию (например, для заработка: "Сколько ты зарабатываешь в месяц?")
- Второй вопрос должен выяснить планы/намерения/барьеры (например, для заработка: "В какой нише ты зарабатываешь или пытаешься зарабатывать? Может быть ты только ищешь такую нишу?")
- Не используй звездочки или markdown форматирование
- Верни только 2 вопроса, каждый с новой строки, пронумерованные от 1 до 2

Примеры вопросов для разных сфер:
- Заработок: "Сколько ты зарабатываешь в месяц?" и "В какой нише ты зарабатываешь или пытаешься зарабатывать? Может быть ты только ищешь такую нишу?"
- Здоровье/Тело: "Какой у тебя текущий уровень физической активности?" и "Какие конкретные цели по здоровью ты хочешь достичь?"
- Разум: "Как часто ты занимаешься саморазвитием и обучением?" и "Какие навыки или знания ты хочешь развить в первую очередь?"
- Отношения: "Как ты оцениваешь качество своих текущих отношений?" и "Что конкретно ты хочешь улучшить в отношениях?"
- Коммуникации: "Насколько уверенно ты чувствуешь себя в общении?" и "В каких ситуациях общения тебе сложнее всего?" """

        try:
            response = await client.chat.completions.create(
                model=settings.OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=400
            )
            
            result = response.choices[0].message.content
            
            # Парсим вопросы (каждый с новой строки, пронумерованные)
            questions = []
            lines = result.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Убираем markdown форматирование из строки
                line = clean_markdown(line)
                
                # Проверяем, начинается ли строка с цифры (номер вопроса)
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # Убираем номер и маркеры
                    import re
                    # Убираем номер в начале (1., 1), 2., 2) и т.д.)
                    question = re.sub(r'^\d+[\.\)]\s*', '', line)
                    # Убираем маркеры (-, •)
                    question = question.lstrip('- ').lstrip('• ').strip()
                    if question and len(question) > 10:
                        questions.append(question)
            
            # Если не удалось распарсить достаточно вопросов, пробуем другой подход
            if len(questions) < 2:
                # Пробуем найти вопросы по другим паттернам
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    line = clean_markdown(line)
                    # Если строка длинная и не является заголовком, это может быть вопрос
                    if len(line) > 15 and line not in questions:
                        # Проверяем, что это не служебный текст
                        if not any(x in line.lower() for x in ['верни', 'формат', 'сгенерируй', 'создай', 'пример']):
                            questions.append(line)
            
            # Если все еще мало вопросов, используем дефолтные вопросы для сферы
            if len(questions) < 2:
                # Дефолтные вопросы для разных сфер
                default_questions = {
                    "Заработок": [
                        "Сколько ты зарабатываешь в месяц?",
                        "В какой нише ты зарабатываешь или пытаешься зарабатывать? Может быть ты только ищешь такую нишу?"
                    ],
                    "Здоровье/Тело": [
                        "Какой у тебя текущий уровень физической активности?",
                        "Какие конкретные цели по здоровью ты хочешь достичь?"
                    ],
                    "Разум": [
                        "Как часто ты занимаешься саморазвитием и обучением?",
                        "Какие навыки или знания ты хочешь развить в первую очередь?"
                    ],
                    "Отношения": [
                        "Как ты оцениваешь качество своих текущих отношений?",
                        "Что конкретно ты хочешь улучшить в отношениях?"
                    ],
                    "Коммуникации": [
                        "Насколько уверенно ты чувствуешь себя в общении?",
                        "В каких ситуациях общения тебе сложнее всего?"
                    ]
                }
                
                questions = default_questions.get(sphere, [
                    f"Расскажи о своей текущей ситуации в сфере {sphere}.",
                    f"Какие конкретные цели у тебя есть в сфере {sphere}?"
                ])
            
            # Добавляем вопросы для текущей сферы
            for question in questions[:2]:  # Берем максимум 2 вопроса
                all_questions.append({
                    "sphere": sphere,
                    "question": question
                })
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка при генерации вопросов для сферы {sphere}: {e}", exc_info=True)
            # Используем дефолтные вопросы при ошибке
            default_questions = {
                "Заработок": [
                    "Сколько ты зарабатываешь в месяц?",
                    "В какой нише ты зарабатываешь или пытаешься зарабатывать? Может быть ты только ищешь такую нишу?"
                ],
                "Здоровье/Тело": [
                    "Какой у тебя текущий уровень физической активности?",
                    "Какие конкретные цели по здоровью ты хочешь достичь?"
                ],
                "Разум": [
                    "Как часто ты занимаешься саморазвитием и обучением?",
                    "Какие навыки или знания ты хочешь развить в первую очередь?"
                ],
                "Отношения": [
                    "Как ты оцениваешь качество своих текущих отношений?",
                    "Что конкретно ты хочешь улучшить в отношениях?"
                ],
                "Коммуникации": [
                    "Насколько уверенно ты чувствуешь себя в общении?",
                    "В каких ситуациях общения тебе сложнее всего?"
                ]
            }
            
            questions = default_questions.get(sphere, [
                f"Расскажи о своей текущей ситуации в сфере {sphere}.",
                f"Какие конкретные цели у тебя есть в сфере {sphere}?"
            ])
            
            for question in questions[:2]:
                all_questions.append({
                    "sphere": sphere,
                    "question": question
                })
    
    return all_questions


async def generate_roadmap(
    goal_3months: str,
    basic_answers: Dict,
    detailed_answers: Dict,
    role_model: str
) -> Dict:
    """Генерирует роадмап достижения цели на 3 месяца.
    
    На основе цели пользователя, его ответов и ролевой модели создает
    роадмап с промежуточными milestone (недели 1-2, 3-4, 5-8, 9-12).
    
    Args:
        goal_3months (str): Цель пользователя на 3 месяца
        basic_answers (Dict): Базовые ответы пользователя
        detailed_answers (Dict): Развернутые ответы пользователя
        role_model (str): Выбранная ролевая модель
        
    Returns:
        Dict: Словарь с роадмапом:
            - weeks_1_2: {"goal": str, "result": str, "actions": List[str]}
            - weeks_3_4: {"goal": str, "result": str, "actions": List[str]}
            - weeks_5_8: {"goal": str, "result": str, "actions": List[str]}
            - weeks_9_12: {"goal": str, "result": str, "actions": List[str]}
        
    Example:
        .. code-block:: python
        
            roadmap = await generate_roadmap(
                goal_3months="Заработать 100к в месяц",
                basic_answers={...},
                detailed_answers={...},
                role_model="andrew_tate"
            )
    """
    personality_key = _map_role_model_to_personality(role_model)
    personality_data = get_personality_prompt(personality_key)
    personality_name = personality_data.get("name", role_model)
    personality_description = personality_data.get("description", "")
    
    prompt = f"""Ты - {personality_name}, наставник пользователя. Создай краткий роадмап достижения цели пользователя на 3 месяца, используя ТВОЙ подход, ТВОЮ философию и ТВОЙ стиль.

{personality_description}

Цель пользователя: {goal_3months}

Информация о пользователе:
- Пол: {basic_answers.get('gender', 'не указано')}
- Возраст: {basic_answers.get('age', 'не указано')}
- Ценности: {', '.join(basic_answers.get('values', []))}
- Сферы развития: {', '.join(basic_answers.get('development_spheres', []))}

Развернутые ответы пользователя:
{chr(10).join([f"{k}: {v}" for k, v in detailed_answers.items()])}

КРИТИЧЕСКИ ВАЖНО: Создай роадмап так, как бы это сделал {personality_name}. Используй:
- ТВОЙ подход к достижению целей
- ТВОЮ философию и методы работы
- ТВОЙ стиль общения и манеру речи
- ТВОИ принципы и ценности
- ТВОЙ способ мотивации

Создай краткий роадмап на 4 этапа. Для каждого этапа напиши ОДНУ фразу в 20-30 слов, которая описывает что мы добьёмся на этом этапе, используя ТВОЙ подход.

КРИТИЧЕСКИ ВАЖНО - Формат ответа (строго соблюдай, каждая неделя на отдельной строке):
НЕДЕЛЯ 1-2: [одна фраза в 20-30 слов о том, что добьёмся, в стиле {personality_name}]

НЕДЕЛЯ 3-4: [одна фраза в 20-30 слов о том, что добьёмся, в стиле {personality_name}]

НЕДЕЛЯ 5-8: [одна фраза в 20-30 слов о том, что добьёмся, в стиле {personality_name}]

НЕДЕЛЯ 9-12: [одна фраза в 20-30 слов о финальной цели, в стиле {personality_name}]

Важно: 
- Каждая неделя должна быть на ОТДЕЛЬНОЙ строке
- Каждая фраза должна быть краткой (20-30 слов), мотивирующей и конкретной
- Говори КАК {personality_name}, используй его стиль общения, манеру речи, подход и философию
- Не используй звездочки, маркеры или форматирование
- Не объединяй несколько недель в одну строку - каждая неделя должна быть отдельно"""

    response = await client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": personality_data["system_prompt"]},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1500
    )
    
    result = response.choices[0].message.content
    
    # Убираем звездочки и markdown форматирование
    result = clean_markdown(result)
    
    # Парсим роадмап - теперь это просто текст для каждой недели
    roadmap = {
        "weeks_1_2": {"text": ""},
        "weeks_3_4": {"text": ""},
        "weeks_5_8": {"text": ""},
        "weeks_9_12": {"text": ""}
    }
    
    # Улучшенный парсинг: сначала пытаемся найти маркеры недель в тексте
    # GPT может вернуть все в одной строке или с разными разделителями
    
    # Ищем паттерны типа "НЕДЕЛЯ 1-2:", "НЕДЕЛЯ 3-4:" и т.д.
    import re
    
    # Паттерны для поиска недель
    week_patterns = {
        "weeks_1_2": re.compile(r'НЕДЕЛЯ\s*1-2\s*:?\s*(.+?)(?=НЕДЕЛЯ\s*3-4|НЕДЕЛЯ\s*5-8|НЕДЕЛЯ\s*9-12|$)', re.IGNORECASE | re.DOTALL),
        "weeks_3_4": re.compile(r'НЕДЕЛЯ\s*3-4\s*:?\s*(.+?)(?=НЕДЕЛЯ\s*5-8|НЕДЕЛЯ\s*9-12|$)', re.IGNORECASE | re.DOTALL),
        "weeks_5_8": re.compile(r'НЕДЕЛЯ\s*5-8\s*:?\s*(.+?)(?=НЕДЕЛЯ\s*9-12|$)', re.IGNORECASE | re.DOTALL),
        "weeks_9_12": re.compile(r'НЕДЕЛЯ\s*9-12\s*:?\s*(.+?)$', re.IGNORECASE | re.DOTALL),
    }
    
    # Пробуем найти по паттернам
    for week_key, pattern in week_patterns.items():
        match = pattern.search(result)
        if match:
            text = match.group(1).strip()
            # Очищаем от лишних пробелов и переносов строк
            text = ' '.join(text.split())
            # Убираем маркеры других недель, если они попали в текст
            text = re.sub(r'НЕДЕЛЯ\s*\d+[-–]\d+.*$', '', text, flags=re.IGNORECASE).strip()
            if text:
                roadmap[week_key]["text"] = text
    
    # Если паттерны не сработали, пробуем построчный парсинг
    if not any(roadmap[k]["text"] for k in roadmap.keys()):
        lines = result.split('\n')
        current_week = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Определяем неделю
            if re.search(r'НЕДЕЛЯ\s*1[-–]?2', line, re.IGNORECASE):
                current_week = "weeks_1_2"
                # Извлекаем текст после маркера недели
                text = re.sub(r'НЕДЕЛЯ\s*1[-–]?2\s*:?\s*', '', line, flags=re.IGNORECASE).strip()
                if text:
                    roadmap[current_week]["text"] = text
            elif re.search(r'НЕДЕЛЯ\s*3[-–]?4', line, re.IGNORECASE):
                current_week = "weeks_3_4"
                text = re.sub(r'НЕДЕЛЯ\s*3[-–]?4\s*:?\s*', '', line, flags=re.IGNORECASE).strip()
                if text:
                    roadmap[current_week]["text"] = text
            elif re.search(r'НЕДЕЛЯ\s*5[-–]?8', line, re.IGNORECASE):
                current_week = "weeks_5_8"
                text = re.sub(r'НЕДЕЛЯ\s*5[-–]?8\s*:?\s*', '', line, flags=re.IGNORECASE).strip()
                if text:
                    roadmap[current_week]["text"] = text
            elif re.search(r'НЕДЕЛЯ\s*9[-–]?12', line, re.IGNORECASE):
                current_week = "weeks_9_12"
                text = re.sub(r'НЕДЕЛЯ\s*9[-–]?12\s*:?\s*', '', line, flags=re.IGNORECASE).strip()
                if text:
                    roadmap[current_week]["text"] = text
            elif current_week and line:
                # Продолжение текста для текущей недели (только если это не маркер другой недели)
                if not re.search(r'НЕДЕЛЯ\s*\d+', line, re.IGNORECASE):
                    if roadmap[current_week]["text"]:
                        roadmap[current_week]["text"] += " " + line
                    else:
                        roadmap[current_week]["text"] = line
    
    # Проверяем, что все недели имеют текст
    # Если какая-то неделя не заполнена, генерируем дефолтную цель на основе общей цели
    for week_key in ["weeks_1_2", "weeks_3_4", "weeks_5_8", "weeks_9_12"]:
        if not roadmap[week_key]["text"] or roadmap[week_key]["text"].strip() == "":
            # Генерируем дефолтную цель на основе общей цели пользователя
            if week_key == "weeks_1_2":
                roadmap[week_key]["text"] = f"Начать движение к цели: {goal_3months[:50]}"
            elif week_key == "weeks_3_4":
                roadmap[week_key]["text"] = f"Продолжить активные действия для достижения цели"
            elif week_key == "weeks_5_8":
                roadmap[week_key]["text"] = f"Ускорить прогресс и закрепить результаты"
            else:  # weeks_9_12
                roadmap[week_key]["text"] = f"Достичь финальной цели: {goal_3months[:50]}"
        # Очищаем от лишних пробелов
        roadmap[week_key]["text"] = ' '.join(roadmap[week_key]["text"].split())
    
    return roadmap


async def evaluate_report_with_revision(
    user_level: int,
    category: str,
    report_text: str,
    previous_homework: str,
    personality_key: str = "andrew_tate"
) -> tuple[str, int, str, bool]:
    """Оценивает отчет пользователя по ДЗ с возможностью правок.
    
    Отправляет отчет пользователя в GPT через OpenRouter API для оценки.
    GPT анализирует выполнение предыдущего ДЗ и определяет:
    - Выполнено ли ДЗ хорошо (можно переходить к новому)
    - Или требуется переделать с правками
    
    Args:
        user_level (int): Текущий уровень пользователя (0-10)
        category (str): Категория развития пользователя (finances/health/mental)
        report_text (str): Текст отчета пользователя о выполнении ДЗ
        previous_homework (str): Текст предыдущего домашнего задания
        personality_key (str): Ключ личности коуча. По умолчанию andrew_tate.
        
    Returns:
        tuple[str, int, str, bool]: Кортеж из четырех элементов:
            - feedback (str): Обратная связь от GPT по отчету
            - new_level (int): Новый уровень пользователя
            - new_homework_or_revision (str): Новое ДЗ или правки к текущему
            - needs_revision (bool): True если требуется переделать ДЗ, False если можно переходить к новому
        
    Note:
        Если needs_revision=True, то new_homework_or_revision содержит правки к текущему ДЗ.
        Если needs_revision=False, то new_homework_or_revision содержит новое ДЗ для следующего уровня.
    """
    personality_data = get_personality_prompt(personality_key)
    personality_name = personality_data.get("name", "наставник")
    personality_description = personality_data.get("description", "")
    
    # Вычисляем следующий и предыдущий уровни
    next_level = min(user_level + 1, 10)
    prev_level = max(user_level - 1, 0)
    
    # Используем промпт для оценки с возможностью правок
    prompt = f"""Ты - {personality_name}, наставник пользователя. Оцени отчет пользователя по ДЗ уровня {user_level}, категория {category}, используя ТВОЙ подход, ТВОЮ философию и ТВОИ стандарты.

{personality_description}

Предыдущее ДЗ: {previous_homework}

Отчет пользователя: {report_text}

КРИТИЧЕСКИ ВАЖНО: Оцени работу так, как бы это сделал {personality_name}. Используй:
- ТВОИ стандарты качества и выполнения
- ТВОЙ подход к оценке результатов
- ТВОЮ философию и принципы
- ТВОЙ стиль общения и манеру речи
- ТВОЙ способ мотивации и критики

Определи:
1. Выполнено ли ДЗ хорошо по ТВОИМ стандартам? (можно переходить к новому ДЗ уровня {next_level})
2. Или выполнено плохо по ТВОИМ стандартам? (требуются правки к текущему ДЗ)

Если выполнено хорошо → повысь уровень до {next_level} и дай новое ДЗ в ТВОЕМ стиле.
Если выполнено плохо → оставь уровень {user_level} и дай конкретные правки к текущему ДЗ в ТВОЕМ стиле.

Говори КАК {personality_name}. Используй его стиль общения, манеру речи, подход и философию. Кратко, по делу, без воды. Не используй звездочки или markdown форматирование.

Верни ответ строго в формате:
APPROVED: [true/false]
FEEDBACK: [обратная связь в стиле {personality_name}, 2-3 предложения]
NEW_LEVEL: [новый уровень, число]
NEW_HOMEWORK_OR_REVISION: [новое ДЗ для нового уровня ИЛИ конкретные правки к текущему ДЗ в стиле {personality_name}. Если нужны правки (APPROVED: false), укажи ЧТО ИМЕННО нужно исправить и КАК это сделать, используя ТВОЙ подход. Будь конкретным и дай четкие инструкции. Не оставляй это поле пустым.]

ВАЖНО: Если требуется переделка (APPROVED: false), в NEW_HOMEWORK_OR_REVISION укажи конкретные действия, что нужно сделать для исправления, используя ТВОЙ подход и методы. Перечисли по пунктам, что именно не так и как это исправить."""

    response = await client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": personality_data["system_prompt"]},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=800
    )
    
    result = response.choices[0].message.content
    result = clean_markdown(result)
    
    # Парсим ответ
    feedback = result
    new_level = user_level
    new_homework_or_revision = ""
    needs_revision = True  # По умолчанию требуются правки
    
    lines = result.split('\n')
    
    if "APPROVED:" in result:
        approved_line = [line for line in lines if 'APPROVED:' in line]
        if approved_line:
            approved_text = approved_line[0].split('APPROVED:')[-1].strip().lower()
            needs_revision = 'false' in approved_text or 'нет' in approved_text or 'no' in approved_text
    
    if "FEEDBACK:" in result:
        feedback_start_idx = None
        for i, line in enumerate(lines):
            if 'FEEDBACK:' in line:
                feedback_start_idx = i
                break
        
        if feedback_start_idx is not None:
            # Берем текст после маркера в той же строке
            feedback_text = lines[feedback_start_idx].split('FEEDBACK:')[-1].strip()
            
            # Добавляем все последующие строки до следующего маркера или до конца
            for i in range(feedback_start_idx + 1, len(lines)):
                next_line = lines[i].strip()
                # Останавливаемся, если встретили следующий маркер
                if next_line.startswith(('APPROVED:', 'FEEDBACK:', 'NEW_LEVEL:', 'NEWLEVEL:', 'NEW_HOMEWORK_OR_REVISION:', 'NEWHOMEWORKORREVISION:')):
                    break
                # Пропускаем пустые строки в начале
                if not feedback_text and not next_line:
                    continue
                # Добавляем строку к тексту
                if feedback_text:
                    feedback_text += '\n' + next_line
                else:
                    feedback_text = next_line
            
            feedback = feedback_text.strip()
    
    # Ищем NEW_LEVEL или NEWLEVEL (без подчеркивания)
    if "NEW_LEVEL:" in result or "NEWLEVEL:" in result:
        level_line = [line for line in lines if 'NEW_LEVEL:' in line or 'NEWLEVEL:' in line]
        if level_line:
            try:
                # Извлекаем число из строки
                level_text = level_line[0]
                if 'NEW_LEVEL:' in level_text:
                    level_text = level_text.split('NEW_LEVEL:')[-1].strip()
                elif 'NEWLEVEL:' in level_text:
                    level_text = level_text.split('NEWLEVEL:')[-1].strip()
                # Извлекаем первое число из текста
                import re
                numbers = re.findall(r'\d+', level_text)
                if numbers:
                    new_level = int(numbers[0])
            except:
                new_level = user_level
    
    # Ищем NEW_HOMEWORK_OR_REVISION или NEWHOMEWORKORREVISION (без подчеркиваний)
    if "NEW_HOMEWORK_OR_REVISION:" in result or "NEWHOMEWORKORREVISION:" in result:
        homework_start_idx = None
        marker_found = None
        for i, line in enumerate(lines):
            if 'NEW_HOMEWORK_OR_REVISION:' in line:
                homework_start_idx = i
                marker_found = 'NEW_HOMEWORK_OR_REVISION:'
                break
            elif 'NEWHOMEWORKORREVISION:' in line:
                homework_start_idx = i
                marker_found = 'NEWHOMEWORKORREVISION:'
                break
        
        if homework_start_idx is not None:
            # Берем текст после маркера в той же строке
            homework_text = lines[homework_start_idx].split(marker_found)[-1].strip()
            
            # Добавляем все последующие строки до следующего маркера или до конца
            for i in range(homework_start_idx + 1, len(lines)):
                next_line = lines[i].strip()
                # Останавливаемся, если встретили следующий маркер
                if next_line.startswith(('APPROVED:', 'FEEDBACK:', 'NEW_LEVEL:', 'NEWLEVEL:', 'NEW_HOMEWORK_OR_REVISION:', 'NEWHOMEWORKORREVISION:')):
                    break
                # Пропускаем пустые строки в начале
                if not homework_text and not next_line:
                    continue
                # Добавляем строку к тексту
                if homework_text:
                    homework_text += '\n' + next_line
                else:
                    homework_text = next_line
            
            new_homework_or_revision = homework_text.strip()
    
    # Ограничиваем уровень максимумом 10
    new_level = min(new_level, 10)
    
    return feedback, new_level, new_homework_or_revision, needs_revision


async def generate_first_homework(
    basic_answers: Dict,
    detailed_answers: Dict,
    goal_3months: str,
    roadmap: Dict,
    role_model: str
) -> str:
    """Генерирует первое домашнее задание после завершения опросника.
    
    На основе всех данных пользователя (ответы, цель, роадмап) и ролевой модели
    генерирует первое персональное ДЗ уровня 0, соответствующее первому этапу роадмапа.
    
    Args:
        basic_answers (Dict): Базовые ответы пользователя
        detailed_answers (Dict): Развернутые ответы пользователя
        goal_3months (str): Цель на 3 месяца
        roadmap (Dict): Роадмап достижения цели
        role_model (str): Выбранная ролевая модель
        
    Returns:
        str: Текст первого домашнего задания уровня 0
        
    Example:
        .. code-block:: python
        
            homework = await generate_first_homework(
                basic_answers={...},
                detailed_answers={...},
                goal_3months="Заработать 100к в месяц",
                roadmap={...},
                role_model="andrew_tate"
            )
    """
    personality_key = _map_role_model_to_personality(role_model)
    personality_data = get_personality_prompt(personality_key)
    personality_name = personality_data.get("name", role_model)
    personality_description = personality_data.get("description", "")
    
    # Определяем категорию на основе сфер развития
    development_spheres = basic_answers.get("development_spheres", [])
    category = "finances"  # по умолчанию
    if "Здоровье/Тело" in development_spheres:
        category = "health"
    elif "Разум" in development_spheres or "Коммуникации" in development_spheres:
        category = "mental"
    
    # Получаем первый этап роадмапа
    first_stage = roadmap.get("weeks_1_2", {})
    first_stage_text = first_stage.get("text", "")
    
    prompt = f"""Ты - {personality_name}, наставник пользователя. Создай ОДНО первое домашнее задание уровня 0, используя ТВОЙ подход, ТВОЮ философию и ТВОЙ стиль.

{personality_description}

Информация о пользователе:
- Имя: {basic_answers.get('name', 'пользователь')}
- Возраст: {basic_answers.get('age', 'не указано')}
- Ценности: {', '.join(basic_answers.get('values', []))}
- Сферы развития: {', '.join(basic_answers.get('development_spheres', []))}
- Цель на 3 месяца: {goal_3months}

Первый этап роадмапа (недели 1-2): {first_stage_text}

Развернутые ответы пользователя:
{chr(10).join([f"- {k}: {v}" for k, v in detailed_answers.items()])}

КРИТИЧЕСКИ ВАЖНО: Создай задание так, как бы это сделал {personality_name}. Используй:
- ТВОЙ подход к обучению и развитию
- ТВОЮ философию и методы работы
- ТВОЙ стиль общения и манеру речи
- ТВОИ принципы и ценности
- ТВОЙ способ мотивации и постановки задач

Создай ОДНО первое ДЗ уровня 0, которое:
1. Соответствует первому этапу роадмапа
2. Учитывает опыт и возможности пользователя из развернутых ответов
3. Мотивирует и дает быстрый результат (в ТВОЕМ стиле)
4. Выполнимо за 1-2 дня
5. Имеет конкретный формат отчета (что нужно предоставить после выполнения)
6. Отражает ТВОЙ подход к достижению целей

ВАЖНО: Верни ТОЛЬКО ОДНО задание. Не создавай несколько заданий (DZ0, DZ1, DZ2 и т.д.). Только одно задание уровня 0.

Говори КАК {personality_name}. Используй его стиль общения, манеру речи, подход и философию. Кратко, по делу, без воды. Не используй звездочки или markdown форматирование.

Верни только текст ОДНОГО ДЗ, без дополнительных комментариев, без нумерации заданий."""

    response = await client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": personality_data["system_prompt"]},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    homework = response.choices[0].message.content.strip()
    homework = clean_markdown(homework)
    return homework

