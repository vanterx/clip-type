"""
ClipType — hotkey-triggered clipboard typer.
All settings live in config.json (same directory as this script).
"""

import json
import logging
import sys
import threading
import winreg
from pathlib import Path
from typing import TypedDict

import keyboard
import pyperclip
import pystray
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_PATH = Path(__file__).parent / "cliptype.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Config(TypedDict):
    hotkey: str
    char_delay_ms: int
    max_length: int
    strip_trailing_newlines: bool
    multiline: str          # "allow" | "strip" | "warn"
    confirm_above: int      # 0 = disabled
    confirm_delay_ms: int
    run_on_startup: bool


DEFAULTS: Config = {
    "hotkey": "ctrl+shift+f9",
    "char_delay_ms": 10,
    "max_length": 500,
    "strip_trailing_newlines": True,
    "multiline": "allow",
    "confirm_above": 100,
    "confirm_delay_ms": 1500,
    "run_on_startup": False,
}

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        return DEFAULTS.copy()
    try:
        with CONFIG_PATH.open() as f:
            return {**DEFAULTS, **json.load(f)}  # type: ignore[return-value]
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not load config.json (%s) — using defaults", exc)
        return DEFAULTS.copy()


def save_config(data: Config) -> None:
    try:
        with CONFIG_PATH.open("w") as f:
            json.dump(data, f, indent=2)
    except OSError as exc:
        log.error("Could not save config.json: %s", exc)


cfg = load_config()

# ---------------------------------------------------------------------------
# Windows startup registry
# ---------------------------------------------------------------------------

_REG_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "ClipType"


def _startup_cmd() -> str:
    pythonw = Path(sys.executable).parent / "pythonw.exe"
    script = Path(__file__).resolve()
    return f'"{pythonw}" "{script}"'


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN) as k:
            winreg.QueryValueEx(k, _APP_NAME)
            return True
    except OSError:
        return False


def set_startup(enable: bool) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_RUN, 0, winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, _startup_cmd())
            else:
                try:
                    winreg.DeleteValue(k, _APP_NAME)
                except OSError:
                    pass
    except OSError as exc:
        log.error("Could not update startup registry key: %s", exc)

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

_icon: pystray.Icon | None = None
_pause_event = threading.Event()        # set = paused
_typing_lock = threading.Lock()
_cancel_event = threading.Event()       # set during confirm delay to cancel typing
_cfg_lock = threading.Lock()            # guards mutations of cfg

# ---------------------------------------------------------------------------
# Icon
# ---------------------------------------------------------------------------

_ICON_SIZE = 64
_ICON_MARGIN = 2
_COLOR_ACTIVE: tuple[int, int, int] = (0, 120, 212)
_COLOR_PAUSED: tuple[int, int, int] = (160, 160, 160)
_TEXT_OFFSET = (14, 18)


def make_icon(paused: bool = False) -> Image.Image:
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse(
        [_ICON_MARGIN, _ICON_MARGIN, _ICON_SIZE - _ICON_MARGIN, _ICON_SIZE - _ICON_MARGIN],
        fill=_COLOR_PAUSED if paused else _COLOR_ACTIVE,
    )
    draw.text(_TEXT_OFFSET, "CT", fill="white")
    return img

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _notify(message: str) -> None:
    if _icon:
        try:
            _icon.notify(message, "ClipType")
        except Exception as exc:
            log.warning("Tray notification failed: %s", exc)


def _mask(text: str) -> str:
    """Return first 3 chars then bullet placeholders, capped at 20 total."""
    show = min(3, len(text))
    hidden = min(len(text) - show, 17)
    return text[:show] + "•" * hidden

# ---------------------------------------------------------------------------
# Text preparation
# ---------------------------------------------------------------------------

def _prepare_text(raw: str) -> str | None:
    """
    Normalise and validate clipboard text.
    Returns the cleaned string to type, or None to abort.
    """
    text = raw.rstrip("\r\n") if cfg["strip_trailing_newlines"] else raw

    if "\n" in text or "\r" in text:
        mode = cfg["multiline"]
        if mode == "strip":
            text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        elif mode == "warn":
            log.info("Blocked — clipboard has multiple lines (%d chars)", len(text))
            _notify(f"Blocked — clipboard has multiple lines ({len(text)} chars)")
            return None

    if len(text) > cfg["max_length"]:
        log.info("Blocked — text too long (%d chars, max %d)", len(text), cfg["max_length"])
        _notify(f"Blocked — too long ({len(text)} chars, max {cfg['max_length']})")
        return None

    return text


# ---------------------------------------------------------------------------
# Typing
# ---------------------------------------------------------------------------

def _do_type(text: str) -> None:
    """Handle confirm delay then send keystrokes."""
    confirm_above = cfg["confirm_above"]
    if confirm_above > 0 and len(text) > confirm_above:
        delay_s = cfg["confirm_delay_ms"] / 1000
        log.debug("Confirm delay %.1fs for %d chars", delay_s, len(text))
        _notify(f"Typing {len(text)} chars in {cfg['confirm_delay_ms']} ms…  (pause to cancel)")
        _cancel_event.clear()
        cancelled = _cancel_event.wait(timeout=delay_s)
        if cancelled or _pause_event.is_set():
            log.info("Typing cancelled during confirm delay")
            return

    log.debug("Typing %d chars", len(text))
    keyboard.write(text, delay=cfg["char_delay_ms"] / 1000)

    summary = f"{len(text)} chars  •  {_mask(text)}"
    if _icon:
        _icon.title = f"ClipType  •  last: {summary}"
    log.info("Typed %s", summary)
    _notify(f"Done — typed {summary}")


def type_clipboard() -> None:
    if _pause_event.is_set():
        return

    if not _typing_lock.acquire(blocking=False):
        log.debug("Already typing — ignoring re-trigger")
        return

    try:
        # Small pause so modifier keys physically release
        _cancel_event.wait(timeout=0.15)

        raw = pyperclip.paste()
        if not raw:
            log.debug("Clipboard is empty")
            return

        text = _prepare_text(raw)
        if text is None:
            return

        _do_type(text)

    except Exception as exc:
        log.exception("Unexpected error during typing: %s", exc)
        _notify(f"Error: {exc}")
    finally:
        _typing_lock.release()


def on_hotkey() -> None:
    threading.Thread(target=type_clipboard, daemon=True).start()

# ---------------------------------------------------------------------------
# Tray actions
# ---------------------------------------------------------------------------

def toggle_pause(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    if _pause_event.is_set():
        _pause_event.clear()
        log.info("Resumed")
    else:
        _pause_event.set()
        _cancel_event.set()   # interrupt any in-progress confirm delay
        log.info("Paused")

    paused = _pause_event.is_set()
    icon.icon = make_icon(paused=paused)
    icon.title = f"ClipType  ({'paused' if paused else cfg['hotkey']})"
    icon.update_menu()


def toggle_startup(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    enabled = not is_startup_enabled()
    set_startup(enabled)
    with _cfg_lock:
        cfg["run_on_startup"] = enabled
        save_config(cfg)
    log.info("Start with Windows: %s", enabled)


def on_exit(icon: pystray.Icon, _item: pystray.MenuItem) -> None:
    log.info("Exiting")
    keyboard.unhook_all_hotkeys()
    icon.stop()   # unblocks _icon.run() in main(); sys.exit not needed

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global _icon

    log.info("ClipType starting — hotkey: %s", cfg["hotkey"])
    keyboard.add_hotkey(cfg["hotkey"], on_hotkey)

    # Sync registry with config on startup
    if cfg["run_on_startup"] != is_startup_enabled():
        set_startup(cfg["run_on_startup"])

    menu = pystray.Menu(
        pystray.MenuItem(f"ClipType  •  {cfg['hotkey'].upper()}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Pause", toggle_pause, checked=lambda _: _pause_event.is_set()),
        pystray.MenuItem("Start with Windows", toggle_startup, checked=lambda _: is_startup_enabled()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit),
    )

    _icon = pystray.Icon("ClipType", make_icon(), f"ClipType  ({cfg['hotkey']})", menu)
    _icon.run()
    log.info("ClipType stopped")


if __name__ == "__main__":
    main()
