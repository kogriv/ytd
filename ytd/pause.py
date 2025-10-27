"""Управление паузами между загрузками."""
from __future__ import annotations

import sys
import threading
from typing import Optional

import typer


class PauseController:
    """Контроллер пауз с поддержкой клавиатурного управления.
    
    Позволяет приостановить загрузку между элементами плейлиста
    нажатием клавиши во время загрузки текущего элемента.
    """
    
    def __init__(self, pause_key: str = "p", resume_key: str = "r"):
        """Инициализировать контроллер пауз.
        
        Args:
            pause_key: Клавиша для запроса паузы (по умолчанию 'p')
            resume_key: Клавиша для возобновления (по умолчанию 'r')
        """
        self.pause_key = pause_key.lower()
        self.resume_key = resume_key.lower()
        self._pause_requested = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_listener = threading.Event()
        self._enabled = False
    
    def enable(self) -> None:
        """Включить слушатель клавиатуры."""
        if self._enabled:
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
    
    def _keyboard_listener(self) -> None:
        """Слушать нажатия клавиш в фоновом потоке (только Windows)."""
        # Используем msvcrt для Windows (встроенный модуль)
        # Для Linux/macOS нужна альтернатива (termios, tty)
        try:
            import msvcrt
        except ImportError:
            # Не Windows - пропускаем слушатель
            return
        
        while not self._stop_listener.is_set():
            if msvcrt.kbhit():
                try:
                    char = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    if char == self.pause_key:
                        self._pause_requested.set()
                        # Мгновенно показываем индикатор запроса паузы
                        typer.secho(
                            f"\n⏸  Пауза запрошена (будет применена после текущей загрузки)...",
                            fg=typer.colors.YELLOW
                        )
                except Exception:
                    # Игнорируем ошибки декодирования и прочее
                    pass
            # Небольшая задержка для снижения нагрузки на CPU
            self._stop_listener.wait(timeout=0.1)
    
    def is_pause_requested(self) -> bool:
        """Проверить, была ли запрошена пауза."""
        return self._pause_requested.is_set()
    
    def wait_if_paused(self) -> None:
        """Если пауза запрошена, показать промпт и ждать нажатия клавиши возобновления."""
        if not self._pause_requested.is_set():
            return
        
        typer.echo("\n" + "═" * 60)
        typer.secho("⏸  ПАУЗА", fg=typer.colors.YELLOW, bold=True)
        typer.echo("═" * 60)
        typer.secho(
            f"Нажмите '{self.resume_key}' для возобновления или Ctrl+C для выхода...",
            fg=typer.colors.CYAN
        )
        
        # Ждём нажатия клавиши возобновления
        try:
            import msvcrt
        except ImportError:
            # Не Windows - fallback на input()
            typer.prompt("Нажмите Enter для продолжения", default="", show_default=False)
            self._pause_requested.clear()
            typer.secho("▶  Возобновление загрузки...\n", fg=typer.colors.GREEN)
            return
        
        # Windows: ждём клавишу возобновления
        while True:
            if msvcrt.kbhit():
                try:
                    char = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    if char == self.resume_key or char == "\r":  # 'r' или Enter
                        self._pause_requested.clear()
                        typer.secho("▶  Возобновление загрузки...\n", fg=typer.colors.GREEN)
                        return
                except Exception:
                    pass
            # Небольшая задержка
            threading.Event().wait(timeout=0.1)
    
    def reset(self) -> None:
        """Сбросить состояние паузы."""
        self._pause_requested.clear()
    
    def __enter__(self) -> PauseController:
        """Context manager entry."""
        self.enable()
        return self
    
    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.disable()
