"""
NEXUS (упрощённая версия) — точка входа.

Цикл: читаем команду пользователя (текст или голос) -> парсер
определяет Intent -> диспетчер вызывает нужный Tool -> печатаем
результат.

Это прообраз будущего Agent Engine: Intent сейчас определяется
парсером по ключевым словам, а не LLM, но структура (parser -> tool)
та же самая, что будет и в полной версии с function calling.
"""
import sys

# На некоторых Windows-консолях (особенно старый cmd.exe с нестандартной
# кодовой страницей) кириллица может отображаться битыми символами.
# Принудительно переключаем стандартные потоки на UTF-8, если это возможно.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr, sys.stdin):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

from nexus import config
from nexus.parser import Intent, parse_command
from nexus.tools import ai_agent, apps, files, tts, voice, web

HELP_TEXT = """NEXUS — простой агент управления ПК (Windows)

Примеры команд:
  открой блокнот
  открой калькулятор
  открой ютуб / открой хабр / открой авито (можно неточно/разговорно)
  открой сайт stackoverflow.com
  открой pycharm / открой steam / открой мафия
  открой vpn  (открывает Happ)
  покажи рабочий стол  (диагностика: что видит NEXUS)
  найди приложение happ  (диагностика: где нашёл бы, без запуска)
  найди файл report.docx
  найди файл report.docx на диске D

Команды: помощь / голос / ai статус / ai вкл / ai выкл / ai тест <фраза> /
         звук вкл / звук выкл / голоса / выход
  голос — переключиться на голосовой ввод (нужен микрофон и pip install
          SpeechRecognition PyAudio, см. README)
  ai статус/вкл/выкл — локальный AI-агент через Ollama (см. README).
          Если Ollama не запущена, NEXUS сам использует обычный парсер.
  ai тест <фраза> — показать сырой ответ модели (для диагностики)
  звук вкл/выкл — озвучка коротких ответов вслух (нужен pip install
          pyttsx3, см. README)
  голоса — показать список голосов, установленных в системе
"""

VOICE_EXIT_PHRASES = ("текстовый режим", "вернись в текст", "стоп голос", "текст")
QUIT_PHRASES = ("выход", "exit", "quit")


_APP_NOT_FOUND_PREFIX = "Не удалось найти или открыть"


def _resolve_intent(user_input: str) -> Intent:
    """Сначала пробуем быстрый парсер по ключевым словам — если он
    уверенно понял команду (действие не "unknown"), используем его
    результат сразу, БЕЗ обращения к AI-модели вообще. Локальная модель
    всё равно отвечает не мгновенно (даже прогретая — от долей секунды
    до пары секунд), так что нет смысла спрашивать её о командах,
    которые парсер и так понимает мгновенно (все кнопки быстрого
    доступа устроены именно так — начинаются с чёткого триггер-слова).

    AI-агент подключается только тогда, когда парсер НЕ смог понять
    фразу (например разговорную, без привычных триггер-слов) — то есть
    именно там, где от него есть реальная польза, а не просто задержка."""
    quick_intent = parse_command(user_input)
    if quick_intent.action != "unknown":
        return quick_intent

    if config.USE_AI_AGENT:
        raw = ai_agent.ask_agent(user_input)
        if raw:
            return Intent(
                action=raw.get("action", "unknown"),
                target=raw.get("target"),
                extra=raw.get("extra") or {},
            )
    return quick_intent


_MAX_SPEAK_LENGTH = 220  # длинные ответы (списки файлов, справка) не озвучиваем — долго и не нужно


def _maybe_speak(result: str) -> None:
    """Озвучивает результат, если включено и он достаточно короткий —
    списки файлов/справку/диагностику озвучивать бессмысленно (долго и
    неудобно на слух), поэтому такие ответы пропускаем молча."""
    if not config.TTS_ENABLED or not result:
        return
    if len(result) > _MAX_SPEAK_LENGTH or result.count("\n") > 2:
        return
    tts.speak(result)


def _dispatch_inner(user_input: str) -> str:
    intent = _resolve_intent(user_input)

    if intent.action == "list_desktop":
        return apps.list_desktop_entries()
    if intent.action == "locate_app":
        return apps.locate_application(intent.target)
    if intent.action == "open_app":
        result = apps.open_application(intent.target)
        if result.startswith(_APP_NOT_FOUND_PREFIX):
            # Не нашли как приложение — вполне может быть, что это
            # было название сайта, сказанное разговорно/неточно.
            # Автоматически пробуем открыть его как сайт (с запасным
            # вариантом через поиск Google внутри web.py).
            site_result = web.open_website(intent.target)
            return f"{result}\n\nПохоже, это сайт — пробую так: {site_result}"
        return result
    if intent.action == "open_multiple":
        targets = intent.extra.get("targets", [])
        results = [apps.open_application(t) for t in targets]
        return "\n".join(results)
    if intent.action == "open_site":
        return web.open_website(intent.target)
    if intent.action == "search_files":
        return files.search_files(intent.target, drive=intent.extra.get("drive"))
    return (
        "Не понял команду. Введите 'помощь', чтобы увидеть примеры, "
        "или попробуйте: 'открой <приложение/сайт>' / 'найди файл <имя>'."
    )


def dispatch(user_input: str) -> str:
    """Единая точка выполнения команды. Никогда не бросает исключение
    наружу — любая непредвиденная ошибка превращается в понятное
    сообщение, чтобы одна неудачная команда не обрывала всю программу."""
    try:
        result = _dispatch_inner(user_input)
        _maybe_speak(result)
        return result
    except Exception as exc:
        return (
            f"Произошла непредвиденная ошибка при выполнении команды: {exc}\n"
            f"Программа продолжает работать — попробуйте другую команду."
        )


class ExitNexus(Exception):
    """Сигнал полного завершения программы из вложенного голосового цикла."""


def voice_loop() -> None:
    if not voice.is_available():
        print(
            "NEXUS: Голосовой режим недоступен — не установлены зависимости.\n"
            "Установите их командой:\n"
            "  pip install SpeechRecognition PyAudio\n"
            "(подробности и решение проблем с PyAudio на Windows — в README)\n"
        )
        return

    print(
        "NEXUS: Голосовой режим включён. Говорите команду после надписи "
        "'Слушаю...'. Скажите 'текстовый режим', чтобы вернуться к вводу "
        "с клавиатуры.\n"
    )
    while True:
        try:
            print("Слушаю...")
            text, error = voice.listen_once()

            if text is None:
                print(f"NEXUS: {error}\n")
                continue

            print(f"Вы (голос): {text}")
            lowered = text.lower()

            if any(phrase in lowered for phrase in VOICE_EXIT_PHRASES):
                print("NEXUS: Возвращаюсь в текстовый режим.\n")
                return
            if lowered in QUIT_PHRASES:
                print("Завершение работы NEXUS.")
                raise ExitNexus

            result = dispatch(text)
            print(f"NEXUS: {result}\n")
        except ExitNexus:
            raise
        except Exception as exc:
            print(f"NEXUS: Ошибка в голосовом режиме: {exc}. Продолжаю слушать.\n")


def main() -> None:
    print(HELP_TEXT)
    if config.USE_AI_AGENT:
        ai_agent.warm_up_async()  # прогреваем модель в фоне, пока пользователь читает помощь

    while True:
        try:
            user_input = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы NEXUS.")
            break

        if not user_input:
            continue

        lowered = user_input.lower()
        if lowered in QUIT_PHRASES:
            print("Завершение работы NEXUS.")
            break
        if lowered in ("помощь", "help"):
            print(HELP_TEXT)
            continue
        if lowered in ("голос", "голосовой режим", "voice"):
            try:
                voice_loop()
            except ExitNexus:
                break
            continue
        if lowered == "ai вкл":
            config.USE_AI_AGENT = True
            print("NEXUS: AI-агент включён (используется, если Ollama запущена).\n")
            continue
        if lowered == "ai выкл":
            config.USE_AI_AGENT = False
            print("NEXUS: AI-агент выключен, используется только обычный парсер.\n")
            continue
        if lowered == "ai статус":
            enabled = "включён" if config.USE_AI_AGENT else "выключен"
            reachable = "доступна" if ai_agent.is_available() else "не найдена/не запущена"
            print(f"NEXUS: AI-агент {enabled}. Ollama сейчас {reachable} ({config.OLLAMA_BASE_URL}).\n")
            continue
        if lowered.startswith("ai тест "):
            phrase = user_input[len("ai тест "):].strip()
            print(f"NEXUS: {ai_agent.debug_ask(phrase)}\n")
            continue
        if lowered == "звук вкл":
            config.TTS_ENABLED = True
            print("NEXUS: Озвучка включена.\n")
            continue
        if lowered == "звук выкл":
            config.TTS_ENABLED = False
            print("NEXUS: Озвучка выключена.\n")
            continue
        if lowered == "голоса":
            print(f"NEXUS: {tts.list_voices()}\n")
            continue

        result = dispatch(user_input)
        print(f"NEXUS: {result}\n")


if __name__ == "__main__":
    main()
