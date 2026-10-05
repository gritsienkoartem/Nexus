"""
Tool: search_files

Уровень безопасности: READ (только чтение файловой системы, ничего не
изменяет и не удаляет).
"""
import os
from pathlib import Path
from typing import Optional

MAX_RESULTS = 20
# Собираем на 1 больше лимита, чтобы честно понимать, есть ли ЕЩЁ файлы
# сверх показанных, а не просто гадать по факту достижения лимита.
COLLECT_LIMIT = MAX_RESULTS + 1
DEFAULT_SEARCH_DIRS = ["Desktop", "Documents", "Downloads", "Pictures", "Videos"]


def search_files(query: str, drive: Optional[str] = None) -> str:
    """
    Ищет файлы, в имени которых встречается query (без учёта регистра).

    Если drive указан (например "D") — сканирует весь корень этого диска.
    Иначе — только стандартные пользовательские папки (Desktop, Documents
    и т.д.), чтобы не сканировать весь диск C без явного запроса.
    """
    if not query or not query.strip():
        return "Не указано, какой файл искать."

    query_lower = query.lower().strip()
    results: list[str] = []

    if drive:
        drive = drive.strip().rstrip(":").upper()
        root = Path(f"{drive}:\\")
        if not root.exists():
            return f"Диск {drive}: не найден."
        _walk_and_collect(root, query_lower, results)
    else:
        home = Path.home()
        search_roots = [home / d for d in DEFAULT_SEARCH_DIRS if (home / d).exists()]
        if not search_roots:
            search_roots = [home]
        for root in search_roots:
            _walk_and_collect(root, query_lower, results)
            if len(results) >= COLLECT_LIMIT:
                break

    if not results:
        location = f"на диске {drive}:" if drive else "в стандартных папках пользователя (Desktop, Documents, Downloads...)"
        return (
            f"Файлы, содержащие '{query}', не найдены {location}. "
            f"Попробуйте: 'найди файл {query} на диске D' для поиска по всему диску."
        )

    has_more = len(results) > MAX_RESULTS
    shown = results[:MAX_RESULTS]
    total_shown = len(shown)

    lines = "\n".join(f"  {i + 1}. {path}" for i, path in enumerate(shown))
    header = f"Найдено файлов: {total_shown}{'+' if has_more else ''}"
    suffix = "\n  ... есть ещё, уточните запрос, чтобы сузить поиск" if has_more else ""
    return f"{header}\n{lines}{suffix}"


def _walk_and_collect(root: Path, query_lower: str, results: list[str]) -> None:
    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if query_lower in filename.lower():
                    results.append(str(Path(dirpath) / filename))
                    if len(results) >= COLLECT_LIMIT:
                        return
    except PermissionError:
        return
