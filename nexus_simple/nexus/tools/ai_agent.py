"""
Tool: ai_agent — необязательный "умный" слой поверх обычного парсера.

Использует локально запущенную Ollama (https://ollama.com) — бесплатно
навсегда, работает без интернета, ничего никуда не отправляет: модель
выполняется прямо на компьютере пользователя.

Если Ollama не установлена или не запущена — NEXUS автоматически
откатывается на обычный парсер по ключевым словам (nexus/parser.py).
Это гарантируется на каждом шаге: ask_agent() никогда не бросает
исключение, при любой проблеме просто возвращает None.

Никаких дополнительных pip-пакетов не требуется — общение с Ollama идёт
через встроенный urllib (Ollama сама поднимает локальный HTTP-сервер).

Как это работает: пользовательский текст отправляется модели с
инструкцией вернуть JSON в том же формате, что и Intent из parser.py
(action / target / extra). Если ответ — невалидный JSON или в нём нет
ожидаемых полей, тоже считаем это неудачей и откатываемся на парсер.

ОБ УСКОРЕНИИ ОТВЕТА (см. ask_agent):
- "num_predict" ограничивает длину ответа модели — нам нужен только
  короткий JSON, а не длинное рассуждение, поэтому генерация обрывается
  рано и не тратит время впустую.
- "temperature": 0 убирает случайность — для задачи "разобрать команду
  в JSON" это не только быстрее, но и стабильнее (меньше шанс, что
  модель уйдёт в сторону от формата).
- "keep_alive" держит модель загруженной в памяти дольше между
  запросами — без этого Ollama может выгружать модель, и следующий
  запрос снова ждёт полной загрузки (это самая долгая часть, может
  быть несколько секунд).
- warm_up_async() "прогревает" модель сразу при старте NEXUS в фоновом
  потоке, чтобы первая настоящая команда пользователя не платила за
  загрузку модели в память.
"""
import json
import threading
import urllib.error
import urllib.request
from typing import Optional

from .. import config

# Форматы ответа, которые должна вернуть модель — с примерами, чтобы
# небольшие локальные модели (3B и меньше) держали формат стабильно.
_SYSTEM_PROMPT = """Ты — модуль распознавания команд для программы NEXUS,
которая управляет Windows-компьютером. Тебе дают команду пользователя на
русском языке. Верни ТОЛЬКО JSON (без пояснений, без markdown, без ```),
в одном из следующих форматов:

Открыть приложение:
{"action": "open_app", "target": "<название приложения>"}

Открыть сайт:
{"action": "open_site", "target": "<название или адрес сайта>"}

Открыть несколько приложений сразу:
{"action": "open_multiple", "extra": {"targets": ["app1", "app2"]}}

Найти файл на диске:
{"action": "search_files", "target": "<имя файла>", "extra": {"drive": "<буква диска или null>"}}

Показать содержимое Рабочего стола:
{"action": "list_desktop"}

Найти приложение, не открывая его:
{"action": "locate_app", "target": "<название приложения>"}

Команда непонятна:
{"action": "unknown"}

Примеры:
"открой блокнот" -> {"action": "open_app", "target": "блокнот"}
"хочу зайти на ютуб" -> {"action": "open_site", "target": "ютуб"}
"найди файл отчёт на диске D" -> {"action": "search_files", "target": "отчёт", "extra": {"drive": "D"}}
"запусти стим и хром" -> {"action": "open_multiple", "extra": {"targets": ["steam", "chrome"]}}

Отвечай ТОЛЬКО валидным JSON, ничего больше."""

_KNOWN_ACTIONS = {
    "open_app", "open_site", "open_multiple",
    "search_files", "list_desktop", "locate_app", "unknown",
}

# Сколько токенов максимум разрешаем модели сгенерировать. Нашему JSON
# с запасом хватает 100 — этим мы не даём модели "растекаться мыслью"
# и генерировать заметно дольше, чем нужно.
_MAX_RESPONSE_TOKENS = 100


def is_available() -> bool:
    """Быстрая проверка: запущен ли локально сервер Ollama. Если нет —
    возвращает False почти мгновенно, не подвешивая программу. Используется
    только для отображения статуса в интерфейсе — сама команда через
    ask_agent() эту проверку больше не дублирует (см. ask_agent)."""
    try:
        req = urllib.request.Request(config.OLLAMA_BASE_URL, method="GET")
        urllib.request.urlopen(req, timeout=1.5)
        return True
    except Exception:
        return False


def _build_payload(user_text: str) -> dict:
    return {
        "model": config.OLLAMA_MODEL,
        "prompt": user_text,
        "system": _SYSTEM_PROMPT,
        "format": "json",
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0,
            "num_predict": _MAX_RESPONSE_TOKENS,
        },
    }


def ask_agent(user_text: str) -> Optional[dict]:
    """Спрашивает локальную модель, что имел в виду пользователь.

    Возвращает словарь в формате Intent (action/target/extra) при успехе,
    либо None при ЛЮБОЙ неудаче (сервер недоступен, модель не установлена,
    невалидный JSON, неизвестное action и т.д.) — вызывающий код в этом
    случае должен откатиться на обычный парсер по ключевым словам.

    Специально НЕ делает отдельную проверку is_available() перед запросом —
    раньше это означало два похода к Ollama вместо одного (сначала
    проверить, потом спросить). Если сервер недоступен, сам запрос
    провалится так же быстро (соединение просто отклоняется ОС), так что
    отдельная проверка только замедляла каждую команду без пользы."""
    if not user_text or not user_text.strip():
        return None

    data = json.dumps(_build_payload(user_text)).encode("utf-8")
    req = urllib.request.Request(
        config.OLLAMA_GENERATE_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None

    response_text = raw.get("response", "") if isinstance(raw, dict) else ""
    try:
        intent_dict = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(intent_dict, dict):
        return None
    if intent_dict.get("action") not in _KNOWN_ACTIONS:
        return None

    return intent_dict


def warm_up_async() -> None:
    """Прогревает модель в фоне сразу при старте NEXUS (main.py/gui.py),
    чтобы первая настоящая команда пользователя не ждала загрузки модели
    в память — эта загрузка может занимать несколько секунд и без прогрева
    "съедала" бы время именно у первой команды пользователя."""
    def _warm() -> None:
        try:
            ask_agent("тест")
        except Exception:
            pass

    threading.Thread(target=_warm, daemon=True).start()


def debug_ask(user_text: str) -> str:
    """Диагностика: показывает, что РЕАЛЬНО ответила Ollama, без скрытия
    деталей откатом на парсер. Используется командой 'ai тест <фраза>'."""
    if not is_available():
        return f"Ollama недоступна по адресу {config.OLLAMA_BASE_URL}."

    data = json.dumps(_build_payload(user_text)).encode("utf-8")
    req = urllib.request.Request(
        config.OLLAMA_GENERATE_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return f"Ошибка запроса к Ollama: {exc}"

    response_text = raw.get("response", "") if isinstance(raw, dict) else str(raw)
    return f"Модель '{config.OLLAMA_MODEL}' ответила:\n{response_text}"
