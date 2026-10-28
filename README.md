# J.A.R.V.I.S. Desktop Assistant

A compact, sci-fi inspired desktop command center built with Python and Tkinter. It gives you a typed command console, optional push-to-talk voice input, spoken replies, local notes, timers, quick web search, app launching, and a small system status panel.

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

Voice input needs microphone access and an internet connection for Google speech recognition. Microphone audio is sent to Google for transcription; JARVIS does not store the audio. Text commands and notes stay local. Spoken replies use the computer's installed speech engine through `pyttsx3`.

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

Notes are saved to `jarvis_notes.json` beside the app. Timers run while JARVIS is open. App launch commands are handled locally with fixed, known application names; the assistant does not execute arbitrary shell commands.

## Files

- `jarvis.py` â€” desktop interface and assistant behavior
- `requirements.txt` â€” optional system metrics and voice packages

