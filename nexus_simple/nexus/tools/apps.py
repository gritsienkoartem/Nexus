"""
Tool: open_application

Уровень безопасности: SAFE_WRITE (запуск процесса, но не деструктивное
действие).

ЛОГИКА ПОИСКА (пробуем по очереди, пока что-то не сработает):

  1. Известный системный алиас (config.APP_ALIASES) — для стандартных
     программ Windows/Office (notepad, chrome, excel...).
  2. Файл на Рабочем столе — ЛЮБОЙ файл (.lnk, .exe, .url), в имени
     которого встречается ключевое слово. Учитывает перенос Рабочего
     стола в OneDrive (через реестр Windows, а не угадывание пути).
  3. Ярлык в меню "Пуск" (Start Menu) — рекурсивный поиск .lnk-файлов.
     Это покрывает почти все установленные обычные Windows-программы,
     даже если для них нет иконки на Рабочем столе.
  4. UWP / Store-приложения — через PowerShell Get-StartApps. Это
     покрывает приложения, у которых нет обычного файла-ярлыка вообще
     (упакованные приложения из Microsoft Store).
  5. Последняя попытка — передать слово как есть в os.startfile /
     командную строку (вдруг это уже готовая системная команда).

Почему так сложно: одна иконка на Рабочем столе технически может быть
любым из четырёх типов выше, и заранее не угадать, какой именно.

ОБ УСКОРЕНИИ (см. _CacheEntry и использующие его функции): сканирование
Рабочего стола/меню Пуск и особенно вызов PowerShell (Get-StartApps,
~1-2 сек) — самые медленные части поиска. Если делать их заново при
КАЖДОЙ команде, это ощутимо тормозит программу, хотя список файлов и
установленных программ почти никогда не меняется от команды к команде.
Поэтому результаты кэшируются на несколько минут (см. _CACHE_TTL) —
первая команда после запуска или после истечения кэша будет чуть
медленнее, все последующие — почти мгновенные на этом этапе.
"""
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from .. import config

_EXTENSION_PRIORITY = {".lnk": 0, ".exe": 1, ".url": 2}
_CACHE_TTL = 300  # 5 минут — список программ на ПК за это время почти не меняется


class _CacheEntry:
    """Простой кэш с временем жизни: хранит результат и когда он получен."""

    __slots__ = ("value", "timestamp")

    def __init__(self) -> None:
        self.value = None
        self.timestamp = 0.0

    def is_fresh(self) -> bool:
        return self.value is not None and (time.time() - self.timestamp) < _CACHE_TTL

    def set(self, value) -> None:
        self.value = value
        self.timestamp = time.time()


_desktop_files_cache = _CacheEntry()
_start_menu_files_cache = _CacheEntry()
_uwp_apps_cache = _CacheEntry()


# ---------------------------------------------------------------------------
# Уровень 2: Рабочий стол
# ---------------------------------------------------------------------------

def _registry_desktop_path() -> Optional[Path]:
    """Реальный путь к Рабочему столу из реестра (учитывает перенос папки
    в OneDrive под любым именем/языком) — надёжнее, чем угадывать путь."""
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "Desktop")
        expanded = Path(os.path.expandvars(value))
        return expanded if expanded.exists() else None
    except OSError:
        return None


def _desktop_dirs() -> list[Path]:
    home = Path.home()
    candidates = [
        _registry_desktop_path(),
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Рабочий стол",
    ]
    seen = set()
    result = []
    for path in candidates:
        if path and path.exists() and path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _list_desktop_files(force_refresh: bool = False) -> list[Path]:
    """Список файлов на Рабочем столе с кэшем на _CACHE_TTL секунд."""
    if not force_refresh and _desktop_files_cache.is_fresh():
        return _desktop_files_cache.value

    files: list[Path] = []
    for desktop in _desktop_dirs():
        try:
            files.extend(entry for entry in desktop.iterdir() if entry.is_file())
        except PermissionError:
            continue
    _desktop_files_cache.set(files)
    return files


def _find_desktop_shortcut(search_term: str) -> Optional[Path]:
    search_term = search_term.lower().strip()
    if not search_term:
        return None

    candidates: list[tuple[int, int, Path]] = []
    for entry in _list_desktop_files():
        stem_lower = entry.stem.lower()
        if search_term in stem_lower:
            exact = 0 if stem_lower == search_term else 1
            ext_priority = _EXTENSION_PRIORITY.get(entry.suffix.lower(), 99)
            candidates.append((exact, ext_priority, entry))

    if not candidates:
        return None
    candidates.sort(key=lambda triple: (triple[0], triple[1]))
    return candidates[0][2]


def list_desktop_entries() -> str:
    """Диагностика: показывает всё, что NEXUS видит на Рабочем столе.
    Всегда читает файлы заново (не из кэша) — это осознанная диагностика
    по явному запросу пользователя, должна показывать самое свежее."""
    dirs = _desktop_dirs()
    if not dirs:
        return "Не нашёл ни одной папки Рабочего стола."

    lines = []
    for desktop in dirs:
        lines.append(f"Папка: {desktop}")
        try:
            entries = sorted(desktop.iterdir(), key=lambda p: p.name.lower())
        except PermissionError:
            lines.append("  (нет доступа к этой папке)")
            continue
        for entry in entries:
            if entry.is_file():
                lines.append(f"  {entry.name}")
    _list_desktop_files(force_refresh=True)  # заодно обновляем кэш свежими данными
    return "\n".join(lines) if lines else "Рабочий стол пуст."


# ---------------------------------------------------------------------------
# Уровень 3: меню "Пуск"
# ---------------------------------------------------------------------------

def _start_menu_dirs() -> list[Path]:
    candidates = []
    program_data = os.environ.get("ProgramData")
    appdata = os.environ.get("APPDATA")
    if program_data:
        candidates.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if appdata:
        candidates.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [p for p in candidates if p.exists()]


def _list_start_menu_files() -> list[Path]:
    """Список .lnk-файлов в меню Пуск с кэшем — рекурсивный обход может
    быть заметно медленнее Рабочего стола, если программ много."""
    if _start_menu_files_cache.is_fresh():
        return _start_menu_files_cache.value

    files: list[Path] = []
    for base in _start_menu_dirs():
        try:
            for root, _dirs, filenames in os.walk(base):
                for filename in filenames:
                    if filename.lower().endswith(".lnk"):
                        files.append(Path(root) / filename)
        except PermissionError:
            continue
    _start_menu_files_cache.set(files)
    return files


def _find_start_menu_shortcut(search_term: str) -> Optional[Path]:
    search_term = search_term.lower().strip()
    if not search_term:
        return None

    candidates: list[tuple[int, Path]] = []
    for path in _list_start_menu_files():
        stem_lower = path.stem.lower()
        if search_term in stem_lower:
            exact = 0 if stem_lower == search_term else 1
            candidates.append((exact, path))

    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Уровень 4: UWP / Store-приложения
# ---------------------------------------------------------------------------

def _query_start_apps() -> list[dict]:
    """Возвращает список всех приложений (обычных и Store) через PowerShell,
    с кэшем на _CACHE_TTL секунд — это самая медленная операция во всей
    цепочке поиска (~1-2 сек), кэш экономит это время на повторных
    неудачных поисках в течение одной сессии."""
    if _uwp_apps_cache.is_fresh():
        return _uwp_apps_cache.value

    ps_command = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Get-StartApps | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
        )
    except Exception:
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    apps_list = [data] if isinstance(data, dict) else data
    _uwp_apps_cache.set(apps_list)
    return apps_list


def _find_uwp_app(search_term: str) -> Optional[dict]:
    for app in _query_start_apps():
        if search_term in app.get("Name", "").lower():
            return app
    return None


def _launch_uwp(app: dict) -> bool:
    app_id = app.get("AppID", "")
    if not app_id:
        return False
    try:
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Публичные функции
# ---------------------------------------------------------------------------

def open_application(keyword: str) -> str:
    if not keyword or not keyword.strip():
        return "Не указано, какое приложение открыть."

    keyword_lower = keyword.lower().strip()

    # 0. Быстрый путь: вдруг это уже готовая системная команда (например,
    # parser.py мог передать сюда уже разрешённое значение вроде "calc"
    # или "msedge", которое само по себе не является ключом в APP_ALIASES,
    # но прекрасно запускается напрямую).
    try:
        os.startfile(keyword.strip())
        return f"Открываю: {keyword.strip()}"
    except OSError:
        pass

    # 1. Известный системный алиас
    command = config.APP_ALIASES.get(keyword_lower)
    if command and command != keyword.strip():
        try:
            os.startfile(command)
            return f"Открываю: {command}"
        except OSError:
            pass

    # 2. Файл на Рабочем столе
    search_term = config.DESKTOP_APP_ALIASES.get(keyword_lower, keyword_lower)
    shortcut = _find_desktop_shortcut(search_term)
    if shortcut:
        try:
            os.startfile(str(shortcut))
            return f"Открываю: {shortcut.stem}"
        except OSError:
            pass

    # 3. Ярлык в меню "Пуск"
    start_menu_shortcut = _find_start_menu_shortcut(search_term)
    if start_menu_shortcut:
        try:
            os.startfile(str(start_menu_shortcut))
            return f"Открываю: {start_menu_shortcut.stem}"
        except OSError:
            pass

    # 4. UWP / Store-приложение
    uwp_app = _find_uwp_app(search_term)
    if uwp_app and _launch_uwp(uwp_app):
        return f"Открываю: {uwp_app.get('Name')}"

    # 5. Последняя попытка — через командную строку
    fallback = command or keyword
    try:
        subprocess.Popen(fallback, shell=True)
        return f"Открываю: {fallback} (через командную строку)"
    except Exception as exc:
        return (
            f"Не удалось найти или открыть '{keyword}' ни одним из способов "
            f"(системный алиас / Рабочий стол / меню Пуск / Store). "
            f"Выполните 'найди приложение {keyword}' для диагностики. Ошибка: {exc}"
        )


def locate_application(keyword: str) -> str:
    """Диагностика: где именно NEXUS нашёл бы это приложение — без запуска."""
    if not keyword:
        return "Не указано, какое приложение искать."

    keyword_lower = keyword.lower().strip()
    search_term = config.DESKTOP_APP_ALIASES.get(keyword_lower, keyword_lower)

    command = config.APP_ALIASES.get(keyword_lower)
    if command:
        return f"Найден системный алиас: '{keyword}' -> команда '{command}'"

    shortcut = _find_desktop_shortcut(search_term)
    if shortcut:
        return f"Найден на Рабочем столе: {shortcut}"

    start_menu_shortcut = _find_start_menu_shortcut(search_term)
    if start_menu_shortcut:
        return f"Найден в меню Пуск: {start_menu_shortcut}"

    uwp_app = _find_uwp_app(search_term)
    if uwp_app:
        return f"Найден как Store/системное приложение: {uwp_app.get('Name')}"

    return (
        f"Не нашёл '{keyword}' ни среди системных алиасов, ни на Рабочем "
        f"столе, ни в меню Пуск, ни среди Store-приложений. Проверьте "
        f"точное название командой 'покажи рабочий стол'."
    )
