
from dataclasses import dataclass, field
from typing import Optional
import re

from . import config
from .tools import web


@dataclass
class Intent:
    action: str
    target: Optional[str] = None
    extra: dict = field(default_factory=dict)


def _strip_trigger(text: str, triggers: list[str]) -> Optional[str]:

    lowered = text.lower()
    for trig in sorted(triggers, key=len, reverse=True):
        if lowered.startswith(trig):
            return text[len(trig):].strip()
    return None


def _extract_drive(text: str) -> tuple[str, Optional[str]]:

    match = re.search(r"на диске\s+([a-zA-Zа-яА-Я])", text, flags=re.IGNORECASE)
    if not match:
        return text, None
    drive_letter = match.group(1).upper()
    cleaned = (text[: match.start()] + text[match.end():]).strip()
    return cleaned, drive_letter


def parse_command(text: str) -> Intent:
    text = text.strip()
    text_lower = text.lower()


    for trig in config.LIST_DESKTOP_TRIGGERS:
        if trig in text_lower:
            return Intent(action="list_desktop")


    remainder = _strip_trigger(text, config.LOCATE_TRIGGERS)
    if remainder is not None:
        if not remainder:
            return Intent(action="unknown")
        return Intent(action="locate_app", target=remainder.strip())


    remainder = _strip_trigger(text, config.SEARCH_TRIGGERS)
    if remainder is not None:
        remainder, drive = _extract_drive(remainder)
        if not remainder:
            return Intent(action="unknown")
        return Intent(action="search_files", target=remainder, extra={"drive": drive})


    remainder = _strip_trigger(text, config.OPEN_TRIGGERS)
    if remainder is not None:
        remainder_lower = remainder.lower().strip()


        for alias, targets in config.COMPOSITE_ALIASES.items():
            if alias in remainder_lower:
                return Intent(action="open_multiple", extra={"targets": targets})


        if remainder_lower.startswith("сайт "):
            return Intent(action="open_site", target=remainder[5:].strip())

        if any(hint in remainder_lower for hint in config.SITE_HINT_WORDS):
            return Intent(action="open_site", target=remainder)

        for alias, command in config.APP_ALIASES.items():
            if alias in remainder_lower:
                return Intent(action="open_app", target=command)

        if web.quick_match(remainder):
            return Intent(action="open_site", target=remainder)

        return Intent(action="open_app", target=remainder.strip())

    return Intent(action="unknown")
