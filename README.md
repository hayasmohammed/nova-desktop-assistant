# NOVA â€” Desktop AI Assistant

A sci-fi inspired desktop command center built with Python and Tkinter. The controls are connected to working features: command navigation, editable local notes, live timer countdowns, a session activity log, system metrics, push-to-talk voice input, spoken replies, web search, and fixed app shortcuts. The project is now named **NOVA**. The source file remains `jarvis.py` so existing launch instructions and IDE tabs continue to work.

## Start

1. Install Python 3.10 or newer.
2. In this folder, run:

   ```powershell
   py jarvis.py
   ```

The text command console uses only the Python standard library. Live CPU and memory readings need `psutil`; voice commands and spoken replies are optional add-ons:

```powershell
py -m pip install -r requirements.txt
```

Voice input needs microphone access and an internet connection for Google speech recognition. Microphone audio is sent to Google for transcription; NOVA does not store the audio. Text commands and notes stay local. Spoken replies use the computer's installed speech engine through `pyttsx3`.

If voice packages are installed while NOVA is open, visit **Settings â†’ Check voice packages**. Otherwise restart the app after installing them.

## Commands

- `help`
- `time` or `date`
- `system status`
- `note <something to remember>` or `remember <something>`
- `show notes`
- `timer 5 minutes` or `timer 30 seconds`
- `cancel timer`
- `open YouTube`, `open GitHub`, `open calculator`, `open notepad`
- `search <words>`

Use the sidebar to open **My notes**, **Timers**, **Activity log**, and **Settings**. Notes can be edited or deleted, timers show a live countdown and can be cancelled individually, and the command box recalls previous commands with the up/down arrow keys. Press `Ctrl+L` to jump back to the command box.

Notes are saved to `nova_notes.json` beside the app. Existing `jarvis_notes.json` notes are loaded automatically for migration. Timers run while NOVA is open. The activity log is kept in memory and clears when the app closes. App launch commands are handled locally with fixed, known application names; the assistant does not execute arbitrary shell commands.

## Files

- `jarvis.py` â€” desktop interface and assistant behavior
- `requirements.txt` â€” optional system metrics and voice packages

