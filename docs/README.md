# Генерация HTML документации

## Быстрый старт

### Вариант 1: Использование make.bat (Windows)

```powershell
cd docs
.\make.bat html
```

После генерации откройте файл `build\html\index.html` в браузере.

### Вариант 2: Использование Python напрямую

Если у вас установлен Python и Sphinx:

```powershell
cd docs
python -m sphinx -b html source build/html
```

Или с использованием py launcher:

```powershell
cd docs
py -m sphinx -b html source build/html
```

### Вариант 3: Использование виртуального окружения

Если проект использует виртуальное окружение:

```powershell
# Активируйте виртуальное окружение
.\venv\Scripts\Activate.ps1  # или .venv\Scripts\activate для cmd

# Установите зависимости для документации (если еще не установлены)
pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints sphinxcontrib-napoleon

# Сгенерируйте документацию
cd docs
python -m sphinx -b html source build/html
```

## Открытие документации

После успешной генерации откройте файл:

```
docs\build\html\index.html
```

Или через командную строку:

```powershell
start docs\build\html\index.html
```

## Установка зависимостей для документации

Если Sphinx еще не установлен:

```powershell
pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints sphinxcontrib-napoleon
```

## Структура документации

- `source/conf.py` - конфигурация Sphinx
- `source/index.rst` - главная страница документации
- `source/modules.rst` - описание всех модулей проекта
- `build/html/` - сгенерированная HTML документация
