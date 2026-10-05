"""
Tool: open_website

Уровень безопасности: READ (просто открывает URL в браузере).

Приоритет — Яндекс Браузер, если он найден в стандартных папках
установки Windows. Если не найден или не запустился — используется
браузер по умолчанию (через webbrowser).
"""
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

from .. import config

# Стандартные пути установки Яндекс Браузера на Windows
YANDEX_BROWSER_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Yandex" / "YandexBrowser" / "Application" / "browser.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Yandex" / "YandexBrowser" / "Application" / "browser.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Yandex" / "YandexBrowser" / "Application" / "browser.exe",
]


def _find_yandex_browser() -> Optional[str]:
    for path in YANDEX_BROWSER_PATHS:
        if path.exists():
            return str(path)
    return None


def open_website(url: str) -> str:
    if not url:
        return "Не указано, какой сайт открыть."

    if config.USE_YANDEX_BROWSER:
        yandex_path = _find_yandex_browser()
        if yandex_path:
            try:
                subprocess.Popen([yandex_path, url])
                return f"Открываю в Яндекс Браузере: {url}"
            except Exception:
                pass  # не получилось — попробуем браузер по умолчанию ниже

    try:
        opened = webbrowser.open(url)
        if opened:
            return f"Открываю сайт: {url}"
        return f"Не удалось найти браузер для открытия {url}."
    except Exception as exc:
        return f"Ошибка при открытии сайта {url}: {exc}"
