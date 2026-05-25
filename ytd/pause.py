"""Управление паузами во время и между загрузками."""

from __future__ import annotations

import sys
import threading

import typer

from .console import safe_echo, safe_secho
from .exceptions import IntraVideoPauseRequested


class PauseController:
    """Контроллер пауз с поддержкой клавиатурного управления.

    Режимы:
    - ``between_entries`` — пауза между элементами плейлиста (после текущего файла).
    - ``intra_video`` — прерывание текущей загрузки через progress hook с возобновлением.
    """

    def __init__(
        self,
        pause_key: str = "p",
        resume_key: str = "r",
        *,
        intra_video: bool = False,
        between_entries: bool = True,
    ) -> None:
        self.pause_key = pause_key.lower()
        self.resume_key = resume_key.lower()
        self.intra_video = intra_video
        self.between_entries = between_entries
        self._pause_requested = threading.Event()
        self._listener_thread: threading.Thread | None = None
        self._stop_listener = threading.Event()
        self._enabled = False
        self._keyboard_available = False

    def enable(self) -> None:
        """Включить слушатель клавиатуры."""
        if self._enabled:
            return

        self._keyboard_available = self._stdin_is_interactive()
        if not self._keyboard_available:
            safe_secho(
                "[WARN] Пауза по клавише недоступна: stdin не интерактивный терминал",
                fg=typer.colors.YELLOW,
            )
            return

        self._enabled = True
        self._stop_listener.clear()
        self._listener_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        self._listener_thread.start()

    def disable(self) -> None:
        """Отключить слушатель клавиатуры."""
        if not self._enabled:
            return
        self._enabled = False
        self._stop_listener.set()
        if self._listener_thread:
            self._listener_thread.join(timeout=1.0)
            self._listener_thread = None

    @staticmethod
    def _stdin_is_interactive() -> bool:
        return sys.stdin.isatty()

    def _keyboard_listener(self) -> None:
        """Слушать нажатия клавиш в фоновом потоке."""
        if sys.platform == "win32":
            self._keyboard_listener_windows()
        else:
            self._keyboard_listener_unix()

    def _keyboard_listener_windows(self) -> None:
        try:
            import msvcrt
        except ImportError:
            return

        while not self._stop_listener.is_set():
            if msvcrt.kbhit():
                try:
                    char = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    self._handle_listener_key(char)
                except Exception:
                    pass
            self._stop_listener.wait(timeout=0.1)

    def _keyboard_listener_unix(self) -> None:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._stop_listener.is_set():
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not ready:
                    continue
                char = sys.stdin.read(1)
                if not char:
                    continue
                self._handle_listener_key(char.lower())
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _handle_listener_key(self, char: str) -> None:
        if char != self.pause_key:
            return
        self._pause_requested.set()
        if self.intra_video and self.between_entries:
            message = (
                "\n[PAUSE] Пауза запрошена: текущая загрузка будет прервана "
                "(или пауза после видео в плейлисте)..."
            )
        elif self.intra_video:
            message = (
                "\n[PAUSE] Пауза запрошена: загрузка будет прервана "
                "и продолжена с места остановки..."
            )
        else:
            message = "\n[PAUSE] Пауза запрошена (будет применена после текущей загрузки)..."
        safe_secho(message, fg=typer.colors.YELLOW)

    def check_intra_video_pause_in_hook(self) -> None:
        """Прервать загрузку в progress hook, если запрошена intra-video пауза."""
        if not self.intra_video:
            return
        if self._pause_requested.is_set():
            raise IntraVideoPauseRequested()

    def is_pause_requested(self) -> bool:
        """Проверить, была ли запрошена пауза."""
        return self._pause_requested.is_set()

    def wait_if_paused(self) -> None:
        """Если пауза запрошена, показать промпт и ждать нажатия клавиши возобновления."""
        if not self._pause_requested.is_set():
            return

        safe_echo("\n" + "-" * 60)
        safe_secho("[PAUSE] ПАУЗА", fg=typer.colors.YELLOW, bold=True)
        safe_echo("-" * 60)
        if self.intra_video:
            safe_echo("Загрузка приостановлена. Частичный файл сохранён — продолжение с места остановки.")
        safe_secho(
            f"Нажмите '{self.resume_key}' для возобновления или Ctrl+C для выхода...",
            fg=typer.colors.CYAN,
        )

        if sys.platform == "win32":
            self._wait_for_resume_windows()
        else:
            self._wait_for_resume_unix()

    def _wait_for_resume_windows(self) -> None:
        try:
            import msvcrt
        except ImportError:
            self._wait_for_resume_prompt()
            return

        while True:
            if msvcrt.kbhit():
                try:
                    char = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    if char == self.resume_key or char == "\r":
                        self._clear_pause_and_resume()
                        return
                except Exception:
                    pass
            threading.Event().wait(timeout=0.1)

    def _wait_for_resume_unix(self) -> None:
        if not self._stdin_is_interactive():
            self._wait_for_resume_prompt()
            return

        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if not ready:
                    continue
                char = sys.stdin.read(1)
                if not char:
                    continue
                lowered = char.lower()
                if lowered == self.resume_key or lowered == "\r" or lowered == "\n":
                    self._clear_pause_and_resume()
                    return
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _wait_for_resume_prompt(self) -> None:
        typer.prompt("Нажмите Enter для продолжения", default="", show_default=False)
        self._clear_pause_and_resume()

    def _clear_pause_and_resume(self) -> None:
        self._pause_requested.clear()
        safe_secho("> Возобновление загрузки...\n", fg=typer.colors.GREEN)

    def reset(self) -> None:
        """Сбросить состояние паузы."""
        self._pause_requested.clear()

    def __enter__(self) -> PauseController:
        self.enable()
        return self

    def __exit__(self, *args: object) -> None:
        self.disable()
