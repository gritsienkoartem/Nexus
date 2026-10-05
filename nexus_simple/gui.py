"""
NEXUS — графический интерфейс (без командной строки).

Использует ту же логику, что и main.py (parser -> tools) — просто
другой способ ввода/вывода: окно вместо консоли.

Устройство окна сверху вниз:
  1. Заголовок + статус AI-агента + кнопки помощи/очистки лога
  2. Панель быстрых действий (config.QUICK_ACTIONS) — частые команды
     одним кликом, без набора текста
  3. Лог диалога (прокручиваемый)
  4. Строка ввода: текст + отправить + голос

ВАЖНО про потоки: tkinter однопоточный — если выполнять dispatch()
прямо в обработчике кнопки, всё окно "замерзает" на время выполнения
(поиск приложения может доходить до проверки через PowerShell или
локальную AI-модель — это 1-5 секунд). Поэтому ЛЮБАЯ команда (кнопка,
текст, голос) выполняется в отдельном потоке, а обратно в интерфейс
результат передаётся только через root.after — единственный
потокобезопасный способ обновить tkinter-виджеты из другого потока.
"""
import threading
import tkinter as tk
from tkinter import scrolledtext

from main import HELP_TEXT, dispatch
from nexus import config
from nexus.tools import ai_agent, tts, voice

BG_COLOR = "#1e1e2e"
PANEL_COLOR = "#282838"
TOOLBAR_COLOR = "#242435"
INPUT_BG = "#32324a"
BUTTON_BG = "#32324a"
BUTTON_HOVER = "#3d3d5c"
TEXT_COLOR = "#e0e0e8"
MUTED_COLOR = "#9090a0"
ACCENT_COLOR = "#7c5cff"
USER_COLOR = "#88c0ff"
NEXUS_COLOR = "#7ee787"
OK_COLOR = "#7ee787"
WARN_COLOR = "#f5a742"
ERROR_COLOR = "#ff6b6b"

FONT = ("Segoe UI", 11)
SMALL_FONT = ("Segoe UI", 9)
MONO_FONT = ("Consolas", 10)

VOICE_WORDS = ("голос", "голосовой режим", "voice")
QUICK_ACTION_COLUMNS = 2


class NexusApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._listening = False  # идёт запись голоса
        self._busy = False       # выполняется команда (текстовая или голосовая)

        root.title("NEXUS")
        root.geometry("680x760")
        root.minsize(520, 520)
        root.configure(bg=BG_COLOR)

        self.ai_enabled_var = tk.BooleanVar(value=config.USE_AI_AGENT)
        self.tts_enabled_var = tk.BooleanVar(value=config.TTS_ENABLED)

        self._build_header()
        self._build_quick_actions()
        self._build_output()
        self._build_input()

        self._print_system(HELP_TEXT)
        self._refresh_ai_status()
        if config.USE_AI_AGENT:
            ai_agent.warm_up_async()  # прогреваем модель в фоне сразу при открытии окна

    # -- построение интерфейса ------------------------------------------------

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=PANEL_COLOR)
        header.pack(fill="x")

        title_row = tk.Frame(header, bg=PANEL_COLOR)
        title_row.pack(fill="x", padx=16, pady=(10, 4))

        tk.Label(
            title_row, text="⚡ NEXUS", font=("Segoe UI", 16, "bold"),
            bg=PANEL_COLOR, fg=ACCENT_COLOR,
        ).pack(side="left")

        tk.Label(
            title_row, text="  Локальный агент управления ПК", font=("Segoe UI", 9),
            bg=PANEL_COLOR, fg=MUTED_COLOR,
        ).pack(side="left")

        self._icon_button(title_row, "🗑", "Очистить лог", self._on_clear).pack(side="right", padx=(4, 0))
        self._icon_button(title_row, "❓", "Показать помощь", self._on_help).pack(side="right", padx=(4, 0))

        # -- строка статуса AI-агента: галочка + живой индикатор + обновить --
        status_row = tk.Frame(header, bg=PANEL_COLOR)
        status_row.pack(fill="x", padx=16, pady=(0, 10))

        tk.Checkbutton(
            status_row, text="Использовать AI-агент", variable=self.ai_enabled_var,
            command=self._on_ai_toggle, font=SMALL_FONT, bg=PANEL_COLOR, fg=TEXT_COLOR,
            selectcolor=INPUT_BG, activebackground=PANEL_COLOR, activeforeground=TEXT_COLOR,
            highlightthickness=0, bd=0,
        ).pack(side="left")

        self.ai_status_dot = tk.Label(
            status_row, text="●", font=SMALL_FONT, bg=PANEL_COLOR, fg=MUTED_COLOR,
        )
        self.ai_status_dot.pack(side="left", padx=(12, 2))

        self.ai_status_text = tk.Label(
            status_row, text="проверяю Ollama...", font=SMALL_FONT, bg=PANEL_COLOR, fg=MUTED_COLOR,
        )
        self.ai_status_text.pack(side="left")

        self._icon_button(status_row, "🔄", "Обновить статус", self._refresh_ai_status).pack(side="left", padx=(6, 0))

        tk.Checkbutton(
            status_row, text="🔊 Озвучка", variable=self.tts_enabled_var,
            command=self._on_tts_toggle, font=SMALL_FONT, bg=PANEL_COLOR, fg=TEXT_COLOR,
            selectcolor=INPUT_BG, activebackground=PANEL_COLOR, activeforeground=TEXT_COLOR,
            highlightthickness=0, bd=0,
        ).pack(side="left", padx=(16, 0))

    def _build_quick_actions(self) -> None:
        toolbar = tk.Frame(self.root, bg=TOOLBAR_COLOR)
        toolbar.pack(fill="x")

        inner = tk.Frame(toolbar, bg=TOOLBAR_COLOR)
        inner.pack(fill="x", padx=12, pady=10)
        for col in range(QUICK_ACTION_COLUMNS):
            inner.columnconfigure(col, weight=1)

        for i, action in enumerate(config.QUICK_ACTIONS):
            row, col = divmod(i, QUICK_ACTION_COLUMNS)
            command_text = action["command"].strip()
            btn = tk.Button(
                inner, text=f"{action['icon']}  {command_text}",
                command=lambda a=action: self._on_quick_action(a),
                bg=BUTTON_BG, fg=TEXT_COLOR, activebackground=BUTTON_HOVER,
                activeforeground=TEXT_COLOR, relief="flat", font=SMALL_FONT,
                cursor="hand2", padx=8, pady=8, anchor="w",
            )
            btn.grid(row=row, column=col, sticky="ew", padx=4, pady=4)

    def _build_output(self) -> None:
        self.output = scrolledtext.ScrolledText(
            self.root, wrap="word", bg=BG_COLOR, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR, font=MONO_FONT, borderwidth=0,
            highlightthickness=0, state="disabled", padx=14, pady=10,
        )
        self.output.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self.output.tag_configure("user", foreground=USER_COLOR, font=(MONO_FONT[0], MONO_FONT[1], "bold"))
        self.output.tag_configure("nexus", foreground=NEXUS_COLOR)
        self.output.tag_configure("system", foreground=MUTED_COLOR)

    def _build_input(self) -> None:
        bar = tk.Frame(self.root, bg=PANEL_COLOR)
        bar.pack(fill="x", padx=12, pady=12)

        self.entry = tk.Entry(
            bar, font=FONT, bg=INPUT_BG, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR, relief="flat",
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", lambda _e: self._on_send())
        self.entry.focus_set()

        self.send_button = tk.Button(
            bar, text="Отправить", command=self._on_send, bg=ACCENT_COLOR,
            fg="white", relief="flat", font=FONT, padx=14, cursor="hand2",
            activebackground=ACCENT_COLOR, activeforeground="white",
        )
        self.send_button.pack(side="left")

        self.voice_button = tk.Button(
            bar, text="🎤", command=self._on_voice, bg=INPUT_BG, fg=TEXT_COLOR,
            relief="flat", font=FONT, padx=14, cursor="hand2",
            activebackground=INPUT_BG, activeforeground=TEXT_COLOR,
        )
        self.voice_button.pack(side="left", padx=(8, 0))

    def _icon_button(self, parent: tk.Widget, symbol: str, tooltip: str, command) -> tk.Button:
        return tk.Button(
            parent, text=symbol, command=command, bg=PANEL_COLOR, fg=MUTED_COLOR,
            activebackground=PANEL_COLOR, activeforeground=TEXT_COLOR, relief="flat",
            font=SMALL_FONT, cursor="hand2", bd=0, padx=6,
        )

    # -- вывод в лог ------------------------------------------------------

    def _print(self, text: str, tag: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n", tag)
        self.output.configure(state="disabled")
        self.output.see("end")

    def _print_user(self, text: str) -> None:
        self._print(f"Вы: {text}", "user")

    def _print_nexus(self, text: str) -> None:
        self._print(f"NEXUS: {text}", "nexus")

    def _print_system(self, text: str) -> None:
        self._print(text, "system")

    # -- занятость интерфейса ------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.entry.configure(state=state)
        self.send_button.configure(state=state)

    def _set_voice_button_state(self, listening: bool) -> None:
        self.voice_button.configure(
            text="⏺" if listening else "🎤",
            state="disabled" if listening else "normal",
        )

    # -- заголовок: помощь / очистка / статус AI --------------------------

    def _on_help(self) -> None:
        self._print_system(HELP_TEXT)

    def _on_clear(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _on_ai_toggle(self) -> None:
        config.USE_AI_AGENT = self.ai_enabled_var.get()
        self._refresh_ai_status()

    def _on_tts_toggle(self) -> None:
        config.TTS_ENABLED = self.tts_enabled_var.get()

    def _refresh_ai_status(self) -> None:
        """Проверка доступности Ollama в фоновом потоке — сама проверка
        быстрая (до 1.5 сек), но окно не должно замирать даже на это."""
        self.ai_status_text.configure(text="проверяю...")
        self.ai_status_dot.configure(fg=MUTED_COLOR)

        def worker() -> None:
            reachable = ai_agent.is_available()
            self.root.after(0, lambda: self._apply_ai_status(reachable))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_ai_status(self, reachable: bool) -> None:
        if not config.USE_AI_AGENT:
            self.ai_status_dot.configure(fg=MUTED_COLOR)
            self.ai_status_text.configure(text="выключен")
        elif reachable:
            self.ai_status_dot.configure(fg=OK_COLOR)
            self.ai_status_text.configure(text="Ollama доступна")
        else:
            self.ai_status_dot.configure(fg=WARN_COLOR)
            self.ai_status_text.configure(text="Ollama не найдена — используется обычный парсер")

    # -- быстрые действия ---------------------------------------------------

    def _on_quick_action(self, action: dict) -> None:
        if self._busy or self._listening:
            return
        if action["command"].strip().lower() == "помощь":
            self._on_help()
            return
        if action.get("immediate", True):
            self._print_user(action["command"])
            self._run_command_async(action["command"])
        else:
            # Просто подставляем в поле ввода — команде нужно уточнение
            self.entry.delete(0, "end")
            self.entry.insert(0, action["command"])
            self.entry.focus_set()
            self.entry.icursor("end")

    # -- обработка текстовой команды -----------------------------------------

    def _on_send(self) -> None:
        if self._busy or self._listening:
            return  # уже что-то выполняется — новый ввод игнорируем

        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._print_user(text)

        if text.lower() in VOICE_WORDS:
            self._on_voice()
            return
        if text.lower() in ("помощь", "help"):
            self._on_help()
            return
        if text.lower() == "ai вкл":
            self.ai_enabled_var.set(True)
            self._on_ai_toggle()
            self._print_system("AI-агент включён.")
            return
        if text.lower() == "ai выкл":
            self.ai_enabled_var.set(False)
            self._on_ai_toggle()
            self._print_system("AI-агент выключен, используется только обычный парсер.")
            return
        if text.lower() == "ai статус":
            self._refresh_ai_status()
            return
        if text.lower().startswith("ai тест "):
            phrase = text[len("ai тест "):].strip()
            self._run_ai_debug(phrase)
            return
        if text.lower() == "звук вкл":
            self.tts_enabled_var.set(True)
            self._on_tts_toggle()
            self._print_system("Озвучка включена.")
            return
        if text.lower() == "звук выкл":
            self.tts_enabled_var.set(False)
            self._on_tts_toggle()
            self._print_system("Озвучка выключена.")
            return
        if text.lower() == "голоса":
            self._print_system(tts.list_voices())
            return

        self._run_command_async(text)

    def _run_ai_debug(self, phrase: str) -> None:
        self._set_busy(True)

        def worker() -> None:
            result = ai_agent.debug_ask(phrase)
            self.root.after(0, lambda: self._finish_command(result))

        threading.Thread(target=worker, daemon=True).start()

    def _run_command_async(self, text: str) -> None:
        """Выполняет dispatch() в фоновом потоке, чтобы не подвешивать
        окно — поиск приложения или запрос к AI-модели может занимать
        несколько секунд."""
        self._set_busy(True)

        def worker() -> None:
            try:
                result = dispatch(text)
            except Exception as exc:  # двойная страховка, dispatch и так не должен падать
                result = f"Непредвиденная ошибка интерфейса: {exc}"
            self.root.after(0, lambda: self._finish_command(result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_command(self, result: str) -> None:
        self._set_busy(False)
        self._print_nexus(result)
        self.entry.focus_set()

    # -- обработка голоса ------------------------------------------------

    def _on_voice(self) -> None:
        if not voice.is_available():
            self._print_system(
                "Голосовой режим недоступен. Установите: pip install SpeechRecognition PyAudio"
            )
            return
        if self._listening or self._busy:
            return
        self._listening = True
        self._set_voice_button_state(listening=True)
        self._print_system("Слушаю...")
        threading.Thread(target=self._listen_and_dispatch, daemon=True).start()

    def _listen_and_dispatch(self) -> None:
        """Запись с микрофона тоже в фоновом потоке — иначе окно
        замирает на всё время записи (до 8-10 секунд)."""
        try:
            text, error = voice.listen_once()
        except Exception as exc:
            text, error = None, f"Неожиданная ошибка голосового ввода: {exc}"
        self.root.after(0, lambda: self._finish_voice(text, error))

    def _finish_voice(self, text, error) -> None:
        self._listening = False
        self._set_voice_button_state(listening=False)
        if text is None:
            self._print_system(error)
            return
        self._print_user(f"(голос) {text}")
        self._run_command_async(text)


def main() -> None:
    root = tk.Tk()
    NexusApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
