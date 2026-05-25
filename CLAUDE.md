# ClipType

Windows system-tray utility that types clipboard content as keystrokes via a global hotkey. Built for scenarios where paste is blocked (RDP, legacy apps, password fields).

## Stack

- **Language:** Python 3.12
- **Key libs:** `keyboard`, `pyperclip`, `pystray`, `Pillow`
- **Platform:** Windows only (uses `winreg`, `WScript.Shell`, PyInstaller win build)

## Project Structure

```
cliptype.py       # main app — all logic lives here
config.json       # runtime settings (loaded on startup)
requirements.txt  # pip dependencies
install.bat       # one-time dep install
launch.vbs        # preferred launcher — no cmd window
launch.bat        # terminal launcher (for dev)
dist/ClipType.exe # compiled standalone exe (PyInstaller)
```

## Architecture

```
main()
  └─ keyboard.add_hotkey()       # registers Ctrl+Shift+F9 globally
  └─ pystray.Icon.run()          # message pump + tray icon

on_hotkey()  →  daemon thread  →  type_clipboard()
                                    └─ _prepare_text()   # validate + normalise
                                    └─ _do_type()         # confirm delay + keyboard.write()
```

Key design decisions:
- `_typing_lock` (non-blocking acquire) prevents double-fire if hotkey fires while already typing
- `_pause_event` (`threading.Event`) controls pause/resume safely across threads
- `_cancel_event` (`threading.Event`) lets Pause interrupt the confirm delay mid-sleep
- `_cfg_lock` guards writes to the shared `cfg` dict from the tray callback thread
- `_notify()` wraps `icon.notify()` with a logged fallback — never raises

## Config Keys (`config.json`)

| Key | Default | Notes |
|-----|---------|-------|
| `hotkey` | `ctrl+shift+f9` | Any combo `keyboard` lib understands |
| `char_delay_ms` | `10` | Raise to 30–50 for RDP/VMs |
| `max_length` | `500` | Hard block above this length |
| `strip_trailing_newlines` | `true` | Prevents accidental Enter on passwords |
| `multiline` | `"allow"` | `"strip"` joins lines, `"warn"` blocks |
| `confirm_above` | `100` | Notice + delay before typing long text |
| `confirm_delay_ms` | `1500` | Ms to wait after notice (Pause cancels) |
| `run_on_startup` | `false` | Writes to `HKCU\...\Run` registry key |

## Common Tasks

### Run in dev
```bash
python cliptype.py
```

### Build exe
```bash
pyinstaller --onefile --windowed --name ClipType --add-data "config.json;." cliptype.py
# output: dist/ClipType.exe
```

### Install deps
```bash
pip install -r requirements.txt
```

## Logging

Logs written to `cliptype.log` (same dir as script/exe) and stderr.
Log level: DEBUG. Check this file first when diagnosing silent failures.

## Known Limitations

- Non-ASCII characters (accented, CJK, emoji) are skipped by `keyboard.write()` — it types via virtual key codes
- Requires Python 3.10+ for `str | None` union syntax
- `Start with Windows` registry toggle points to `pythonw.exe` path — will break if Python is moved; use the compiled exe for distribution
