# NOVA — Local Desktop AI Assistant

NOVA is a Windows-first desktop assistant built with Python, HTML, CSS, and JavaScript. It combines a compact always-on-top voice widget with a full chat window, local language-model access, optional web search, and a small set of local productivity tools.

## Features

- **Desktop widget:** Keep NOVA visible above other windows, speak through its microphone, and hover to reveal the expand and quit controls.
- **Voice input and replies:** Speech recognition turns spoken requests into text; NOVA can speak its responses. Code-generation requests are saved as files and get a short spoken confirmation instead of having the code read aloud.
- **Local LLM chat:** Connect to an OpenAI-compatible local server such as LM Studio. Chat requests go to the local server on your computer.
- **Conversation history:** Start separate chats and return to previous conversations. Chat history is stored locally in `nova_chats.json`.
- **Optional live search:** Brave Search can provide current web results to the local model. Search requires a Brave Search API key.
- **Desktop actions:** Use supported commands for notes, timers, opening selected apps and websites, and working with files in allowed user folders. NOVA asks before destructive file operations.
- **Generated projects:** Ask NOVA to create a small web page, game, or code file. Generated files are saved under `Desktop\NOVA Projects`.

## Requirements

- Windows 10 or 11
- Python 3.11 recommended
- [LM Studio](https://lmstudio.ai/) and a downloaded model for AI chat and generation
- A microphone and internet access for Google speech recognition
- Microsoft Edge WebView2 Runtime (usually already installed on Windows)

## Setup

Open PowerShell in the project folder and install the Python packages:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Microphone input also needs PyAudio. On Windows, install its wheel separately:

```powershell
python -m pip install PyAudio==0.2.14
```

If PyAudio fails to install, confirm that the active interpreter is 64-bit Python 3.11. NOVA can open without PyAudio, but microphone input will not work.

Start NOVA:

```powershell
python nova.py
```

## Connect a local model

1. In LM Studio, download a model that fits your computer and load it.
2. Start LM Studio's local server. The default address used by NOVA is `http://127.0.0.1:1234/v1`.
3. Start NOVA and send a message or use the microphone.

To use another local OpenAI-compatible server, set `NOVA_LOCAL_AI_URL` in your environment or local `.env` file. NOVA does not require an OpenAI API key for local chat.

## Optional Brave web search

1. Create a key in the [Brave Search API dashboard](https://api-dashboard.search.brave.com/).
2. Copy `.env.example` to `.env` and set `NOVA_BRAVE_API_KEY` in `.env`.
3. Restart NOVA.

Keep `.env` private. It is ignored by Git and must not be committed. When web search is used, NOVA sends the search query to Brave; retrieved excerpts are passed to the local model for composing the answer. Search is optional.

## Voice and privacy notes

NOVA uses Google's speech recognition service for microphone transcription, which requires internet access. Audio is sent for transcription and is not saved by NOVA. Spoken output uses the configured speech engine and can fall back to the Windows voice if the optional Piper runtime or voice model is unavailable.

Conversation history, notes, and local configuration are kept on the computer. Do not commit `.env`, chat-history files, recordings, or downloaded model files. Review a generated file before running it.

## Example requests

- “What time is it?”
- “Set a timer for 5 minutes.”
- “Remember to submit my assignment.”
- “Search for the latest Python release.”
- “Create a Tic Tac Toe game.”
- “Create a Python script that renames files in a folder.”
- “List the files on my desktop.”

## Project files

| File | Purpose |
| --- | --- |
| `nova.py` | Application entry point |
| `nova_web.py` | Desktop window, voice, assistant actions, and Python bridge |
| `index.html` | Widget and chat interface |
| `nova_ai.py` | Local model requests and optional Brave web search |
| `requirements.txt` | Python dependencies |
| `.env.example` | Safe template for optional local settings |

## Limitations

NOVA is an active personal project. Local model response speed depends on the selected model and computer hardware. The app is designed and documented for Windows; other operating systems may need code changes. Voice transcription relies on an internet service, and Brave Search requires its own API key.
