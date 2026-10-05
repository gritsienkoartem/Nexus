# Если True — сайты открываются в Яндекс Браузере (если он найден),
# иначе сразу используется браузер по умолчанию.
USE_YANDEX_BROWSER = True

# Локальный AI-агент (Ollama, https://ollama.com) — необязательный "умный"
# режим поверх обычного парсера. Полностью бесплатно, работает без
# интернета, ничего никуда не отправляет — модель крутится на твоём ПК.
# Если Ollama не установлена или не запущена, NEXUS автоматически
# откатывается на обычный парсер по ключевым словам — ничего не ломается.
USE_AI_AGENT = True
OLLAMA_MODEL = "llama3.2"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

# Озвучка ответов (текст-в-речь). ПОЛНОСТЬЮ офлайн через встроенный в
# Windows SAPI5 — без единого сетевого запроса, специально ради
# максимальной скорости. Требует: pip install pyttsx3
TTS_ENABLED = True
TTS_RATE = 180  # слов в минуту (обычный темп речи ~150-200)

# Подсказка для выбора голоса — подстрока имени голоса из тех, что
# установлены в Windows (например "Pavel" для мужского русского голоса).
# По умолчанию в Windows для русского предустановлен только женский
# голос "Ирина" — мужской нужно доустановить один раз через:
# Параметры -> Время и язык -> Речь -> Добавить голоса -> Русский.
# Если голос с этой подсказкой не найден — NEXUS возьмёт любой русский
# голос, а если и такого нет — оставит голос по умолчанию.
TTS_VOICE_HINT = "Pavel"

# Алиасы приложений: ключевое слово -> команда запуска (имя exe / зарегистрированное имя)
APP_ALIASES = {
    "блокнот": "notepad",
    "notepad": "notepad",
    "калькулятор": "calc",
    "calculator": "calc",
    "paint": "mspaint",
    "пэйнт": "mspaint",
    "командная строка": "cmd",
    "cmd": "cmd",
    "терминал": "cmd",
    "powershell": "powershell",
    "проводник": "explorer",
    "explorer": "explorer",
    "хром": "chrome",
    "chrome": "chrome",
    "edge": "msedge",
    "эдж": "msedge",
    "word": "winword",
    "ворд": "winword",
    "excel": "excel",
    "эксель": "excel",
    "телеграм": "Telegram.exe",
    "telegram": "Telegram.exe",
    "vscode": "code",
    "vs code": "code",
    "код": "code",
    "steam": "steam",
    "стим": "steam",
    "spotify": "spotify",
    "powerpoint": "powerpnt",
    "поверпоint": "powerpnt",
}

# Русские/короткие алиасы -> подстрока для поиска среди ярлыков на Рабочем
# столе (используется, когда нет надёжной системной команды для запуска).
DESKTOP_APP_ALIASES = {
    "повер поинт": "powerpoint",
    "презентация": "powerpoint",
    "либреофис": "libreoffice",
    "либре офис": "libreoffice",
    "пайчарм": "pycharm",
    "нвидиа": "nvidia",
    "видеокарта": "nvidia",
    "яндекс музыка": "яндекс музыка",
    "музыка": "яндекс музыка",
    "яндекс браузер": "yandex",
    "торрент": "torrent",
    "utorrent": "torrent",
    "хап": "happ",
    "тимвьювер": "teamviewer",
    "тим вьювер": "teamviewer",
    "энидеск": "anydesk",
    "телемост": "телемост",
    "радмин": "radmin",
    "radmin vpn": "radmin",
    "хойка": "hearts of iron",
    "hoi4": "hearts of iron",
    "хартс оф айрон": "hearts of iron",
    "кс2": "counter-str",
    "кс 2": "counter-str",
    "контр страйк": "counter-str",
    "cs2": "counter-str",
    "мафия": "mafia",
    "элиен изоляция": "alien",
    "alien isolation": "alien",
    "тлаунчер": "tlauncher",
}

# Составные команды: одно ключевое слово открывает сразу несколько
# приложений по очереди.
COMPOSITE_ALIASES = {
    "впн": ["happ"],
    "vpn": ["happ"],
}

# Кнопки быстрого доступа в графическом интерфейсе (gui.py). Каждая —
# словарь с иконкой, подписью и командой. Если "immediate": False —
# команда просто подставляется в поле ввода с пробелом на конце, а
# курсор становится готов к вводу (для команд, которым нужно уточнение —
# какое приложение/сайт/файл). Если "immediate": True — выполняется
# сразу по клику, без уточнений.
QUICK_ACTIONS = [
    {"icon": "📂", "label": "Открыть приложение", "command": "открой ", "immediate": False},
    {"icon": "🌐", "label": "Открыть сайт", "command": "открой сайт ", "immediate": False},
    {"icon": "🔍", "label": "Найти файл", "command": "найди файл ", "immediate": False},
    {"icon": "🖥", "label": "Рабочий стол", "command": "покажи рабочий стол", "immediate": True},
    {"icon": "📍", "label": "Где программа", "command": "найди приложение ", "immediate": False},
    {"icon": "🔒", "label": "VPN", "command": "открой happ", "immediate": True},
    {"icon": "🤖", "label": "Тест AI", "command": "ai тест ", "immediate": False},
    {"icon": "❓", "label": "Помощь", "command": "помощь", "immediate": True},
]

# Алиасы сайтов: ключевое слово -> URL
SITE_ALIASES = {
    "ютуб": "https://youtube.com",
    "youtube": "https://youtube.com",
    "гугл": "https://google.com",
    "google": "https://google.com",
    "гитхаб": "https://github.com",
    "github": "https://github.com",
    "почта": "https://mail.google.com",
    "gmail": "https://mail.google.com",
    "почта яндекс": "https://mail.yandex.ru",
    "яндекс почта": "https://mail.yandex.ru",
    "вк": "https://vk.com",
    "vk": "https://vk.com",
    "вконтакте": "https://vk.com",
    "одноклассники": "https://ok.ru",
    "яндекс": "https://ya.ru",
    "yandex": "https://ya.ru",
    "яндекс карты": "https://yandex.ru/maps",
    "карты": "https://yandex.ru/maps",
    "гугл карты": "https://maps.google.com",
    "переводчик": "https://translate.yandex.ru",
    "перевод": "https://translate.yandex.ru",
    "чатгпт": "https://chat.openai.com",
    "chatgpt": "https://chat.openai.com",
    "авито": "https://avito.ru",
    "озон": "https://ozon.ru",
    "вайлдберриз": "https://wildberries.ru",
    "wildberries": "https://wildberries.ru",
    "алиэкспресс": "https://aliexpress.com",
    "aliexpress": "https://aliexpress.com",
    "википедия": "https://ru.wikipedia.org",
    "wikipedia": "https://ru.wikipedia.org",
    "дзен": "https://dzen.ru",
    "netflix": "https://netflix.com",
    "нетфликс": "https://netflix.com",
    "twitch": "https://twitch.tv",
    "твич": "https://twitch.tv",
    "reddit": "https://reddit.com",
    "редит": "https://reddit.com",
    "discord": "https://discord.com",
    "дискорд": "https://discord.com",
    "spotify": "https://open.spotify.com",
    "хабр": "https://habr.com",
    "habr": "https://habr.com",
    "stackoverflow": "https://stackoverflow.com",
    "figma": "https://figma.com",
    "notion": "https://notion.so",
}

# Ключевые слова-триггеры команд (сортировка по длине важна для парсера)
OPEN_TRIGGERS = ["открыть", "открой", "запустить", "запусти"]
SEARCH_TRIGGERS = [
    "найди файлы",
    "найти файлы",
    "поиск файлов",
    "найди файл",
    "найти файл",
    "поиск файла",
]
SITE_HINT_WORDS = ["сайт", "site", ".com", ".ru", ".org", ".net", "www."]

# Диагностическая команда: показать, какие файлы NEXUS видит на Рабочем столе
LIST_DESKTOP_TRIGGERS = ["покажи рабочий стол", "список ярлыков", "какие есть ярлыки", "покажи ярлыки"]

# Диагностическая команда: найти приложение, но не открывать его
LOCATE_TRIGGERS = ["где найти", "найди приложение", "найди программу", "где программа", "где приложение"]
