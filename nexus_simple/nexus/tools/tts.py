"""
Tool: text-to-speech (озвучка ответов NEXUS)

Использует pyttsx3 — работает ПОЛНОСТЬЮ офлайн через встроенный в
Windows SAPI5. Ни одного сетевого запроса, ни одной задержки на сеть —
это осознанный выбор именно ради максимальной скорости ответа.

Требует установки: pip install pyttsx3
(на некоторых системах дополнительно требуется pywin32 — pyttsx3 сам
подскажет об этом при ошибке импорта win32com).

О выборе голоса: по умолчанию Windows предустанавливает для русского
языка только женский голос ("Ирина"). Мужской голос ("Павел") нужно
один раз доустановить через Параметры Windows — см. README. После
установки NEXUS сам его найдёт по подсказке из config.TTS_VOICE_HINT.

Об архитектуре: озвучка — необязательное усиление, а не обязательная
часть работы NEXUS. Если pyttsx3 не установлен — speak() просто молча
ничего не делает, программа продолжает работать как обычно (текстом).
speak() всегда выполняется в отдельном потоке, чтобы не задерживать
основную программу на время произнесения фразы.
"""
import threading
from typing import Optional

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

from .. import config

_engine = None
_engine_init_lock = threading.Lock()
_speak_lock = threading.Lock()  # чтобы две фразы не звучали одновременно внахлёст


def is_available() -> bool:
    return pyttsx3 is not None


def _get_engine():
    """Создаёт движок один раз и переиспользует — повторная инициализация
    pyttsx3 при каждой фразе была бы значительно медленнее."""
    global _engine
    if _engine is None:
        with _engine_init_lock:
            if _engine is None:  # повторная проверка внутри лока
                _engine = pyttsx3.init()
                _engine.setProperty("rate", config.TTS_RATE)
                _apply_voice(_engine)
    return _engine


def _apply_voice(engine) -> None:
    """Пытается выбрать голос по подсказке config.TTS_VOICE_HINT
    (например "Pavel"), иначе — любой голос с пометкой русского языка,
    иначе оставляет голос по умолчанию (обычно женский)."""
    hint = (config.TTS_VOICE_HINT or "").lower().strip()
    try:
        voices = engine.getProperty("voices") or []
    except Exception:
        return

    if hint:
        for voice in voices:
            if hint in (voice.name or "").lower():
                engine.setProperty("voice", voice.id)
                return

    for voice in voices:
        name_lower = (voice.name or "").lower()
        langs = " ".join(str(lang) for lang in (voice.languages or [])).lower()
        if "рус" in name_lower or "russ" in name_lower or "ru-ru" in langs or "ru_ru" in langs:
            engine.setProperty("voice", voice.id)
            return
    # Ничего не нашли — оставляем голос по умолчанию, это не ошибка.


def list_voices() -> str:
    """Диагностика: показывает все голоса, установленные в системе —
    удобно, чтобы узнать точное имя мужского голоса для TTS_VOICE_HINT."""
    if not is_available():
        return "pyttsx3 не установлен. Выполните: pip install pyttsx3"
    try:
        engine = _get_engine()
        voices = engine.getProperty("voices") or []
    except Exception as exc:
        return f"Не удалось получить список голосов: {exc}"

    if not voices:
        return "В системе не найдено ни одного голоса для озвучки."
    lines = [f"  {i}. {v.name}" for i, v in enumerate(voices)]
    return "Доступные голоса в системе:\n" + "\n".join(lines)


def speak(text: str) -> None:
    """Озвучивает текст в фоновом потоке — не блокирует программу.
    Если pyttsx3 не установлен, тихо ничего не делает."""
    if not is_available() or not text or not text.strip():
        return

    def worker() -> None:
        with _speak_lock:
            try:
                engine = _get_engine()
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass  # озвучка необязательна — сбой тут не должен ничего ломать

    threading.Thread(target=worker, daemon=True).start()
