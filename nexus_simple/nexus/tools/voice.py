"""
Tool: voice recognition (распознавание голосовых команд)

Требует установки дополнительных зависимостей (их нет в стандартной
библиотеке Python):

    pip install SpeechRecognition PyAudio

Использует бесплатный анонимный Google Web Speech API через библиотеку
SpeechRecognition. Требует интернет-соединение и работающий микрофон.

listen_once() возвращает пару (текст, ошибка):
  - При успехе: (распознанный текст, None)
  - При неудаче: (None, понятное объяснение причины на русском)

Так вызывающий код (main.py / gui.py) всегда может показать пользователю
конкретную причину — "нет интернета", "не расслышал", "нет микрофона" —
вместо одного и того же неинформативного "не расслышал, попробуйте ещё раз".
"""
from typing import List, Optional, Tuple

try:
    import speech_recognition as sr
except ImportError:
    sr = None


def is_available() -> bool:
    """Проверяет, установлена ли библиотека SpeechRecognition."""
    return sr is not None


def list_microphones() -> List[str]:
    """Список названий доступных микрофонов (для диагностики)."""
    if sr is None:
        return []
    try:
        return sr.Microphone.list_microphone_names()
    except Exception:
        return []


def listen_once(
    language: str = "ru-RU",
    timeout: float = 8.0,
    phrase_time_limit: float = 10.0,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Слушает микрофон один раз.

    Возвращает (текст, ошибка):
      - успех: ("открой блокнот", None)
      - неудача: (None, "человеко-понятное объяснение, что пошло не так")
    """
    if sr is None:
        return None, (
            "Библиотека SpeechRecognition не установлена. "
            "Выполните: pip install SpeechRecognition PyAudio"
        )

    recognizer = sr.Recognizer()
    # Небольшой запас по паузе перед тем как считать фразу законченной —
    # иначе распознавание может обрезать конец медленно произнесённой фразы.
    recognizer.pause_threshold = 0.8

    try:
        mic_names = sr.Microphone.list_microphone_names()
    except Exception:
        mic_names = []
    if not mic_names:
        return None, (
            "Не нашёл ни одного микрофона в системе. Проверьте, что "
            "микрофон подключён и разрешён в Параметры -> Конфиденциальность -> Микрофон."
        )

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    except sr.WaitTimeoutError:
        return None, "Не услышал речь вовремя — истёк таймаут ожидания. Попробуйте начать говорить сразу после 'Слушаю...'."
    except OSError as exc:
        return None, f"Микрофон недоступен: {exc}"

    try:
        text = recognizer.recognize_google(audio, language=language)
        return text, None
    except sr.UnknownValueError:
        return None, "Услышал звук, но не смог разобрать слова. Говорите чуть громче и чётче."
    except sr.RequestError as exc:
        return None, f"Не удалось связаться со службой распознавания речи (нужен интернет). Ошибка: {exc}"
