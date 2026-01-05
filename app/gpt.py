"""OpenRouter API клиент для анализа опросов и генерации ДЗ.

Модуль предоставляет функции для работы с GPT через OpenRouter API:
анализ ответов опросника, генерация развернутых вопросов, роадмапа и оценка отчетов пользователей.
"""
from openai import AsyncOpenAI
from app.config import settings
from app.prompts import get_personality_prompt
from app.prompts.system import SYSTEM_PROMPT
from typing import List, Dict
import re
import logging

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
    """Удаляет только звездочки для выделения текста, сохраняя остальное форматирование.
    
    Args:
        text (str): Текст с возможным markdown форматированием
        
    Returns:
        str: Текст без звездочек для выделения, но с сохранением остального форматирования
    """
    if not text:
        return text
    
    import re
    
    # Убираем только звездочки для выделения текста (bold/italic)
    # 1. Удаляем двойные звездочки ** для bold
    text = text.replace('**', '')
    
    # 2. Удаляем одиночные звездочки * для italic
    # Сохраняем звездочки в начале строки (для списков markdown: "* пункт")
    # Удаляем звездочки, которые используются для выделения текста (*текст*)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Если строка начинается с "* " (список), сохраняем звездочку
        if line.strip().startswith('* '):
            # Удаляем только звездочки внутри текста, но сохраняем первую для списка
            cleaned_line = '* ' + re.sub(r'\*', '', line[2:])
            cleaned_lines.append(cleaned_line)
        else:
            # Для остальных строк удаляем все звездочки
            cleaned_line = line.replace('*', '')
            cleaned_lines.append(cleaned_line)
    
    text = '\n'.join(cleaned_lines)
    
    # НЕ удаляем и сохраняем:
    # - Заголовки (#, ##, ###)
    # - Списки (-, 1.)
    # - Код (` и ```)
    # - Подчеркивания (__ и _)
    # - Другие markdown элементы
    
    return text


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
    """Генерирует 3-5 персонализированных вопросов для опросника.
    
    На основе ответов на базовые вопросы (пол, возраст, имя, ценности, сферы)
    генерирует 3-5 вопросов, персонализированных под выбранные сферы развития.
    Каждый вопрос отправляется отдельным сообщением.
    
    Args:
        basic_answers (Dict): Словарь с базовыми ответами:
            - gender: Мужской/Женский
            - age: возраст (int)
            - name: имя (str)
            - values: список из 3 ценностей
            - development_spheres: список сфер развития
            - goal_3months: цель на 3 месяца (опционально)
        
    Returns:
        List[Dict[str, str]]: Список словарей с вопросами:
            - Каждый словарь содержит: {"sphere": str, "question": str}
            - Всего 3-5 вопросов, распределенных по сферам
        
    Example:
        .. code-block:: python
        
            basic_answers = {
                "gender": "Мужской",
                "age": 25,
                "name": "Иван",
                "values": ["Деньги", "Власть", "Созидание"],
                "development_spheres": ["Заработок", "Разум"],
                "goal_3months": "Заработать 100к в месяц"
            }
            questions = await generate_detailed_questions(basic_answers)
    """
    development_spheres = basic_answers.get('development_spheres', [])
    
    if not development_spheres:
        return []
    
    # Формируем промпт для генерации всех вопросов сразу
    spheres_text = ', '.join(development_spheres)
    goal_text = basic_answers.get('goal_3months', 'не указана')
    
    prompt = f"""Ты - AI-коуч, который проводит персонализированный опросник для создания модели пользователя. Твоя задача - задать 3-5 вопросов, которые идут друг за другом по одному, основываясь на уже известных данных о пользователе и его сферах развития.

ВХОДНЫЕ ДАННЫЕ:
Пол: {basic_answers.get('gender', 'не указано')}
Возраст: {basic_answers.get('age', 'не указано')}
Имя: {basic_answers.get('name', 'не указано')}
Сферы развития пользователя: {spheres_text}
Цель на 3 месяца: {goal_text}

ПРАВИЛА:

Задавай ровно 3-5 вопросов максимум

Каждый вопрос идет отдельной строкой, без нумерации

Вопросы персонализированы под выбранные сферы развития

Пиши обычным текстом без форматирования, звездочек, списков

ЛОГИКА ВОПРОСОВ ПО СФЕРАМ:

Если сфера "Заработок":
Сколько ты зарабатываешь сейчас в месяц?
В какой нише ты зарабатываешь или пытаешься зарабатывать? Или только ищешь такую нишу?
Какой у тебя сейчас основной источник дохода?
Какие навыки ты уже монетизируешь?

Если сфера "Здоровье/Тело":
Какой у тебя текущий уровень физической активности?
Сколько часов в неделю ты тренируешься или двигаешься?
Какой у тебя сейчас вес и какой хочешь достичь?
Какие конкретные цели по здоровью ты ставишь?

Если сфера "Разум":
Как часто ты занимаешься саморазвитием и обучением?
Какие навыки или знания ты хочешь развить в первую очередь?
Сколько книг/курсов/подкастов ты проходишь в месяц?
Что ты изучаешь сейчас?

Если сфера "Отношения":
Как ты оцениваешь качество своих текущих отношений по шкале 1-10?
Сколько близких людей в твоем окружении?
Что конкретно ты хочешь улучшить в отношениях?
Есть ли человек, с которым ты хочешь улучшить коммуникацию?

Если сфера "Коммуникации":
Насколько уверенно ты чувствуешь себя в общении по шкале 1-10?
В каких ситуациях общения тебе сложнее всего?
Сколько новых людей ты знакомишься в месяц?
Что тебя больше всего напрягает в разговорах с незнакомцами?

ПРИМЕР РАБОТЫ:
Пользователь выбрал сферы: Заработок, Здоровье, Разум

ТВОЙ ОТВЕТ:
Привет {basic_answers.get('name', 'пользователь')}! Чтобы понять тебя лучше и дать точные рекомендации, мне нужно уточнить несколько моментов:

Сколько ты зарабатываешь сейчас в месяц?
В какой нише ты зарабатываешь или пытаешься зарабатывать?
Какой у тебя текущий уровень физической активности?
Как часто ты занимаешься саморазвитием и обучением?
Какие навыки ты хочешь развить в первую очередь?

НАЧНИ ОПРОСНИК С УЧЕТОМ ЕГО СФЕР РАЗВИТИЯ ПРЯМО СЕЙЧАС

ВАЖНО: Верни только вопросы, каждый с новой строки, без нумерации, без звездочек. Начни с приветствия и краткого вступления, затем перечисли вопросы."""

    try:
        system_prompt = """Ты - AI-коуч, который проводит персонализированный опросник для создания модели пользователя. Твоя задача - задать 3-5 вопросов, которые идут друг за другом по одному, основываясь на уже известных данных о пользователе и его сферах развития."""

        response = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=600
        )
        
        result = response.choices[0].message.content
        result = clean_markdown(result)
        
        # Парсим вопросы из ответа
        lines = result.split('\n')
        questions = []
        in_questions_section = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Пропускаем приветствие и вступление
            if any(word in line.lower() for word in ['привет', 'здравствуй', 'чтобы понять', 'мне нужно', 'уточнить']):
                in_questions_section = True
                continue
            
            # Если строка похожа на вопрос (содержит знак вопроса или начинается с вопросительного слова)
            if '?' in line or any(line.lower().startswith(word) for word in ['сколько', 'какой', 'какие', 'что', 'как', 'где', 'когда', 'почему', 'кто', 'чем']):
                # Убираем нумерацию и маркеры
                question = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                question = question.lstrip('- ').lstrip('• ').strip()
                if question and len(question) > 10:
                    # Определяем сферу для вопроса
                    sphere = None
                    for dev_sphere in development_spheres:
                        if any(keyword in question.lower() for keyword in get_sphere_keywords(dev_sphere)):
                            sphere = dev_sphere
                            break
                    # Если не определили, берем первую сферу
                    if not sphere:
                        sphere = development_spheres[0]
                    
                    questions.append({
                        "sphere": sphere,
                        "question": question
                    })
        
        # Если не удалось распарсить, пробуем другой подход
        if len(questions) < 3:
            # Берем все строки, которые выглядят как вопросы
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                line = clean_markdown(line)
                if '?' in line and len(line) > 15:
                    question = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                    question = question.lstrip('- ').lstrip('• ').strip()
                    if question and question not in [q["question"] for q in questions]:
                        # Определяем сферу
                        sphere = None
                        for dev_sphere in development_spheres:
                            if any(keyword in question.lower() for keyword in get_sphere_keywords(dev_sphere)):
                                sphere = dev_sphere
                                break
                        if not sphere:
                            sphere = development_spheres[0]
                        
                        questions.append({
                            "sphere": sphere,
                            "question": question
                        })
        
        # Если все еще мало вопросов, используем дефолтные вопросы
        if len(questions) < 3:
            questions = get_default_questions_by_spheres(development_spheres)
        
        # Ограничиваем до 5 вопросов максимум
        return questions[:5]
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при генерации вопросов опросника: {e}", exc_info=True)
        # Используем дефолтные вопросы при ошибке
        return get_default_questions_by_spheres(development_spheres)


def get_sphere_keywords(sphere: str) -> List[str]:
    """Возвращает ключевые слова для определения сферы вопроса.
    
    Args:
        sphere (str): Название сферы развития
        
    Returns:
        List[str]: Список ключевых слов
    """
    keywords_map = {
        "Заработок": ["зарабатываешь", "заработок", "доход", "деньги", "ниша", "монетизируешь", "источник дохода"],
        "Здоровье/Тело": ["физическая активность", "тренируешься", "вес", "здоровье", "двигаешься", "тренировки"],
        "Разум": ["саморазвитие", "обучение", "навыки", "знания", "книги", "курсы", "подкасты", "изучаешь"],
        "Отношения": ["отношения", "близких людей", "окружении", "коммуникацию", "общение"],
        "Коммуникации": ["общении", "общение", "знакомишься", "разговорах", "незнакомцами", "уверенно"]
    }
    return keywords_map.get(sphere, [])


def get_default_questions_by_spheres(spheres: List[str]) -> List[Dict[str, str]]:
    """Возвращает дефолтные вопросы на основе выбранных сфер.
    
    Args:
        spheres (List[str]): Список выбранных сфер развития
        
    Returns:
        List[Dict[str, str]]: Список вопросов с указанием сферы
    """
    default_questions_map = {
        "Заработок": [
            "Сколько ты зарабатываешь сейчас в месяц?",
            "В какой нише ты зарабатываешь или пытаешься зарабатывать? Или только ищешь такую нишу?"
        ],
        "Здоровье/Тело": [
            "Какой у тебя текущий уровень физической активности?",
            "Какие конкретные цели по здоровью ты ставишь?"
        ],
        "Разум": [
            "Как часто ты занимаешься саморазвитием и обучением?",
            "Какие навыки или знания ты хочешь развить в первую очередь?"
        ],
        "Отношения": [
            "Как ты оцениваешь качество своих текущих отношений по шкале 1-10?",
            "Что конкретно ты хочешь улучшить в отношениях?"
        ],
        "Коммуникации": [
            "Насколько уверенно ты чувствуешь себя в общении по шкале 1-10?",
            "В каких ситуациях общения тебе сложнее всего?"
        ]
    }
    
    questions = []
    for sphere in spheres:
        if sphere in default_questions_map:
            for question in default_questions_map[sphere]:
                questions.append({
                    "sphere": sphere,
                    "question": question
                })
    
    # Если вопросов меньше 3, добавляем еще
    if len(questions) < 3 and spheres:
        first_sphere = spheres[0]
        if first_sphere in default_questions_map:
            for question in default_questions_map[first_sphere][:3 - len(questions)]:
                questions.append({
                    "sphere": first_sphere,
                    "question": question
                })
    
    return questions[:5]  # Максимум 5 вопросов


async def generate_roadmap(
    goal_3months: str,
    basic_answers: Dict,
    detailed_answers: Dict,
    role_model: str,
    current_level: int = 0,
    category: str = None
) -> Dict:
    """Генерирует роадмап достижения цели на 3 месяца.
    
    На основе цели пользователя, его ответов и ролевой модели создает
    роадмап с промежуточными milestone (недели 1-3, 4-6, 7-9, 10-12).
    
    Args:
        goal_3months (str): Цель пользователя на 3 месяца
        basic_answers (Dict): Базовые ответы пользователя
        detailed_answers (Dict): Развернутые ответы пользователя
        role_model (str): Выбранная ролевая модель
        current_level (int): Текущий уровень пользователя (по умолчанию 0)
        category (str): Категория развития (finances/health/mental)
        
    Returns:
        Dict: Словарь с роадмапом:
            - stage_1: {"weeks": "1-3", "goal": str, "actions": List[str], "result": str}
            - stage_2: {"weeks": "4-6", "goal": str, "actions": List[str], "result": str}
            - stage_3: {"weeks": "7-9", "goal": str, "actions": List[str], "result": str}
            - stage_4: {"weeks": "10-12", "goal": str, "actions": List[str], "result": str}
            - first_step: str
            - final_result: str
            # Для обратной совместимости также сохраняем старый формат
            - weeks_1_2: {"text": str}
            - weeks_3_4: {"text": str}
            - weeks_5_8: {"text": str}
            - weeks_9_12: {"text": str}
        
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
    
    # Определяем архетип на основе данных пользователя
    values = basic_answers.get('values', [])
    development_spheres = basic_answers.get('development_spheres', [])
    
    # Определяем архетип (упрощенная логика)
    archetype = "Результат-ориентированный"  # по умолчанию
    if "Разум" in development_spheres or "Коммуникации" in development_spheres:
        archetype = "Аналитичный"
    if any(v in ["лидерство", "власть", "влияние"] for v in values):
        archetype = "Лидерский"
    
    # Определяем текущий статус
    current_status = "начинающий"
    if current_level > 3:
        current_status = "есть опыт"
    elif current_level > 0:
        current_status = "есть база"
    
    # Определяем текущий статус для промпта
    status_text = "старт с нуля" if current_status == "начинающий" else "есть база" if current_level > 0 else "есть опыт"
    
    prompt = f"""ПРАВИЛО: Ты — AI-коуч, который строит короткий, конкретный роадмап достижения цели пользователя за 3 месяца (12 недель). Твоя задача — разбить цель на 4 понятных этапа с четкими результатами (milestones), без лишней воды.

ВХОДНЫЕ ДАННЫЕ:
Цель пользователя на 3 месяца: {goal_3months}
Текущий статус: {status_text}

ЗАДАЧА:
1) Разбей цель на 4 логичных этапа:
   Этап 1: старт и базовая валидация
   Этап 2: первые стабильные результаты
   Этап 3: заметный рост
   Этап 4: выход на целевой результат

2) Для каждого этапа укажи только:
   Milestone: один конкретный измеримый результат
   Результат: одна короткая фраза, описывающая смысл этапа

СТРУКТУРА ОТВЕТА:

РОАДМАП НА 3 МЕСЯЦА: {goal_3months}

Этап 1 (1–3 недели)
Milestone: {{конкретный измеримый результат}}
Результат: {{1 короткая фраза}}

Этап 2 (4–6 недели)
Milestone: {{конкретный измеримый результат}}
Результат: {{1 короткая фраза}}

Этап 3 (7–9 недели)
Milestone: {{конкретный измеримый результат}}
Результат: {{1 короткая фраза}}

Этап 4 (10–12 недели)
Milestone: {{конечный целевой результат}}
Результат: {{1 короткая фраза}}

Первый шаг сегодня: {{одно самое логичное действие прямо сейчас}}

ПРАВИЛА ОФОРМЛЕНИЯ:
Markdown: используй текстовые заголовки и абзацы, но не используй символы # и * для форматирования. Ответ должен быть читабельным блоком текста с разделением на строки, как в этом примере."""

    response = await client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": personality_data["system_prompt"]},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    result = response.choices[0].message.content
    
    # Убираем звездочки и markdown форматирование
    result = clean_markdown(result)
    
    # Парсим новый формат роадмапа
    roadmap = {
        "stage_1": {"weeks": "1-3", "goal": "", "actions": [], "result": ""},
        "stage_2": {"weeks": "4-6", "goal": "", "actions": [], "result": ""},
        "stage_3": {"weeks": "7-9", "goal": "", "actions": [], "result": ""},
        "stage_4": {"weeks": "10-12", "goal": "", "actions": [], "result": ""},
        "first_step": "",
        "final_result": "",
        # Для обратной совместимости
        "weeks_1_2": {"text": ""},
        "weeks_3_4": {"text": ""},
        "weeks_5_8": {"text": ""},
        "weeks_9_12": {"text": ""}
    }
    
    # Парсим новый формат роадмапа (Milestone и Результат)
    import re
    
    # Парсим построчно для более точного извлечения
    lines = result.split('\n')
    current_stage = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Определяем этап (поддерживаем разные варианты написания: 1-3, 1–3, 1—3)
        if re.search(r'Этап\s*1\s*\([1-3][–—\-]\s*[1-3]\s*недели?\)', line, re.IGNORECASE):
            current_stage = "stage_1"
        elif re.search(r'Этап\s*2\s*\([4-6][–—\-]\s*[4-6]\s*недели?\)', line, re.IGNORECASE):
            current_stage = "stage_2"
        elif re.search(r'Этап\s*3\s*\([7-9][–—\-]\s*[7-9]\s*недели?\)', line, re.IGNORECASE):
            current_stage = "stage_3"
        elif re.search(r'Этап\s*4\s*\(1[0-2][–—\-]\s*1[0-2]\s*недели?\)', line, re.IGNORECASE):
            current_stage = "stage_4"
        # Определяем Milestone (цель этапа) - может быть на той же или следующей строке
        elif re.search(r'Milestone:', line, re.IGNORECASE) and current_stage:
            milestone_match = re.search(r'Milestone:\s*(.+)', line, re.IGNORECASE)
            if milestone_match:
                milestone_text = milestone_match.group(1).strip()
                if milestone_text:
                    roadmap[current_stage]["goal"] = milestone_text
                # Если на следующей строке есть продолжение
                elif i + 1 < len(lines) and lines[i + 1].strip() and not re.search(r'Результат:', lines[i + 1], re.IGNORECASE):
                    roadmap[current_stage]["goal"] = lines[i + 1].strip()
        # Определяем Результат этапа
        elif re.search(r'Результат:', line, re.IGNORECASE) and current_stage:
            result_match = re.search(r'Результат:\s*(.+)', line, re.IGNORECASE)
            if result_match:
                result_text = result_match.group(1).strip()
                if result_text:
                    roadmap[current_stage]["result"] = result_text
                # Если на следующей строке есть продолжение
                elif i + 1 < len(lines) and lines[i + 1].strip() and not re.search(r'(Этап|Milestone|Первый шаг)', lines[i + 1], re.IGNORECASE):
                    roadmap[current_stage]["result"] = lines[i + 1].strip()
        # Первый шаг
        elif re.search(r'Первый шаг сегодня:', line, re.IGNORECASE):
            step_match = re.search(r'Первый шаг сегодня:\s*(.+)', line, re.IGNORECASE)
            if step_match:
                step_text = step_match.group(1).strip()
                if step_text:
                    roadmap["first_step"] = step_text
                # Если на следующей строке есть продолжение
                elif i + 1 < len(lines) and lines[i + 1].strip():
                    roadmap["first_step"] = lines[i + 1].strip()
    
    # Финальный результат берем из milestone этапа 4
    if roadmap["stage_4"]["goal"]:
        roadmap["final_result"] = roadmap["stage_4"]["goal"]
    
    # Заполняем дефолтные значения, если что-то не распарсилось
    for stage_key in ["stage_1", "stage_2", "stage_3", "stage_4"]:
        if not roadmap[stage_key]["goal"]:
            roadmap[stage_key]["goal"] = f"Продолжить движение к цели: {goal_3months[:50]}"
        if not roadmap[stage_key]["result"]:
            roadmap[stage_key]["result"] = "Прогресс в достижении цели"
    
    if not roadmap["first_step"]:
        roadmap["first_step"] = f"Начать работу над целью: {goal_3months[:50]}"
    if not roadmap["final_result"]:
        roadmap["final_result"] = f"Достижение цели: {goal_3months}"
    
    # Создаем обратно совместимый формат для старого кода
    roadmap["weeks_1_2"]["text"] = roadmap["stage_1"]["goal"]
    roadmap["weeks_3_4"]["text"] = roadmap["stage_2"]["goal"]
    roadmap["weeks_5_8"]["text"] = roadmap["stage_3"]["goal"]
    roadmap["weeks_9_12"]["text"] = roadmap["stage_4"]["goal"]
    
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

ВАЖНО: Если требуется переделка (APPROVED: false), в NEW_HOMEWORK_OR_REVISION укажи конкретные действия, что нужно сделать для исправления, используя ТВОЙ подход и методы. Перечисли по пунктам, что именно не так и как это исправить.

ВАЖНО: Не форматируй текст *. Пиши обычным текстом без звездочек и форматирования."""

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
    
    # Получаем первый этап роадмапа (новый формат или старый для обратной совместимости)
    first_stage = roadmap.get("stage_1", {})
    if first_stage and first_stage.get("goal"):
        first_stage_text = f"{first_stage.get('goal', '')}"
        if first_stage.get('actions'):
            first_stage_text += f" Действия: {', '.join(first_stage.get('actions', [])[:3])}"
    else:
        # Fallback на старый формат
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

Первый этап роадмапа (недели 1-3): {first_stage_text}

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

Верни только текст ОДНОГО ДЗ, без дополнительных комментариев, без нумерации заданий.

ВАЖНО: Не форматируй текст *. Пиши обычным текстом без звездочек и форматирования."""

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

