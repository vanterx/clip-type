# ClipType

[![GitHub Release](https://img.shields.io/github/v/release/vanterx/clip-type)](https://github.com/vanterx/clip-type/releases)

A lightweight Windows tray utility that types your clipboard content as keystrokes — useful anywhere paste is blocked (RDP sessions, password fields, legacy apps).

---

## Download

Grab the latest `ClipType.exe` from the [Releases](https://github.com/vanterx/clip-type/releases) page.
No Python required — double-click and it runs.

---

## Quick Start (from source)

```bash
# 1. Install dependencies (once)
install.bat

# 2. Run
launch.vbs
```

A tray icon appears. Copy text, click into the target field, press **Ctrl+Shift+F9**.

---

## Usage

1. Copy text to clipboard
2. Click into the field where you want to type
3. Press **Ctrl+Shift+F9**
4. ClipType types the text character by character

A balloon notification confirms how many characters were typed.

---

## Tray Menu

| Item | Description |
|------|-------------|
| **Pause** | Suspend the hotkey without exiting. Icon turns grey. Toggle Pause during a confirm delay to cancel mid-type. |
| **Start with Windows** | Toggle auto-start on login (writes to registry). |
| **Exit** | Quit ClipType. |

---

## Configuration

Edit `config.json` in the same folder as the exe. Changes take effect on next launch.

```json
{
  "hotkey": "ctrl+shift+f9",
  "char_delay_ms": 10,
  "max_length": 500,
  "strip_trailing_newlines": true,
  "multiline": "allow",
  "confirm_above": 100,
  "confirm_delay_ms": 1500,
  "run_on_startup": false
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `hotkey` | `ctrl+shift+f9` | Trigger key combo. Any combo the `keyboard` library understands, e.g. `ctrl+alt+v`. |
| `char_delay_ms` | `10` | Milliseconds between keystrokes. Increase to `30`–`50` for RDP or slow VMs. |
| `max_length` | `500` | Hard limit — blocks typing and shows a notification if clipboard exceeds this. |
| `strip_trailing_newlines` | `true` | Removes trailing newlines before typing. Prevents accidental form submission. |
| `multiline` | `"allow"` | What to do when clipboard has multiple lines: `"allow"` types as-is, `"strip"` joins lines with spaces, `"warn"` blocks and notifies. |
| `confirm_above` | `100` | Show a notice and wait before typing if text exceeds this length. Set to `0` to disable. |
| `confirm_delay_ms` | `1500` | How long to wait (ms) after the confirm notice. Toggle Pause during this window to cancel. |
| `run_on_startup` | `false` | Auto-start with Windows. Also toggled via tray menu. |

---

## Requirements

- Windows 10 / 11
- Python 3.10+ (source only — exe has no dependencies)
- Dependencies: `keyboard`, `pyperclip`, `pystray`, `Pillow`

> **Note:** Non-ASCII characters (accented letters, CJK, emoji) are skipped — the `keyboard` library types via virtual key codes which are ASCII-only. Standard passwords and English text work fully.

> **Antivirus false positive:** ClipType registers a global hotkey and simulates keystrokes — the same APIs used by keyloggers. Some AV engines flag it as suspicious. The binary is built with [Nuitka](https://nuitka.net) (compiled C, not a PyInstaller bundle) to minimise false positives, but you may still need to whitelist `ClipType.exe` in your AV. The full source is in this repo for inspection.

---

## Files

```
clip-type/
├── cliptype.py       # main app
├── config.json       # settings
├── requirements.txt  # pip dependencies
├── install.bat       # run once to install deps (source)
├── launch.vbs        # start without a console window
└── launch.bat        # start from terminal
```
