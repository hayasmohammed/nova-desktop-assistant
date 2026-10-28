"""JARVIS â€” a local desktop assistant with a voice-ready command console.

Run with: python jarvis.py
Voice input is optional; install requirements.txt and allow microphone access.
"""
from __future__ import annotations

import json
import os
import platform
import queue
import re
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import END, StringVar, Tk, messagebox
from tkinter import ttk
import tkinter as tk


ROOT = Path(__file__).resolve().parent
NOTES_PATH = ROOT / "jarvis_notes.json"
BG = "#080e15"
SIDE = "#0b131d"
PANEL = "#101b27"
PANEL_HI = "#142332"
LINE = "#1d3343"
CYAN = "#52d7e9"
CYAN_DIM = "#318c9d"
INK = "#e4f1f4"
MUTED = "#829aa7"
GREEN = "#77dfa9"
AMBER = "#e4b96f"
FONT = "Segoe UI"


def load_notes() -> list[dict]:
    try:
        value = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
        return [x for x in value if isinstance(x, dict) and x.get("text")] if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


class Jarvis(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("J.A.R.V.I.S. â€” Personal Desktop Assistant")
        self.geometry("1120x760")
        self.minsize(850, 620)
        self.configure(bg=BG)
        self.notes = load_notes()
        self.command = StringVar()
        self.clock_text = StringVar()
        self.status_text = StringVar(value="ALL SYSTEMS NOMINAL")
        self.listen_text = StringVar(value="VOICE INPUT READY")
        self.speech_queue: queue.Queue[str | None] = queue.Queue()
        self.speech_available = False
        self.active_timers: dict[int, str] = {}
        self._setup_style()
        self._build()
        self._refresh_clock()
        self._refresh_system()
        self._render_notes()
        threading.Thread(target=self._speech_worker, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                        borderwidth=0, rowheight=27, font=(FONT, 9))
        style.configure("Treeview.Heading", background=PANEL_HI, foreground=MUTED,
                        relief="flat", borderwidth=0, font=(FONT, 8, "bold"), padding=(7, 7))
        style.map("Treeview", background=[("selected", "#193949")], foreground=[("selected", INK)])
        style.configure("Vertical.TScrollbar", background=PANEL, troughcolor=PANEL,
                        bordercolor=PANEL, arrowcolor=MUTED)

    def _build(self) -> None:
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(shell, bg=SIDE, width=205, padx=17, pady=21)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        body = tk.Frame(shell, bg=BG, padx=25, pady=19)
        body.pack(side="left", fill="both", expand=True)
        self._build_header(body)
        self._build_main(body)

    def _build_sidebar(self) -> None:
        brand = tk.Frame(self.sidebar, bg=SIDE)
        brand.pack(fill="x", pady=(0, 40))
        mark = tk.Canvas(brand, width=29, height=29, bg=SIDE, highlightthickness=0)
        mark.pack(side="left", padx=(0, 9))
        mark.create_oval(2, 2, 27, 27, outline=CYAN_DIM, width=1)
        mark.create_oval(7, 7, 22, 22, outline=CYAN, width=1)
        mark.create_oval(12, 12, 17, 17, fill=CYAN, outline="")
        tk.Label(brand, text="J.A.R.V.I.S.", bg=SIDE, fg=INK,
                 font=(FONT, 13, "bold")).pack(side="left")
        tk.Label(self.sidebar, text="PERSONAL SYSTEM", bg=SIDE, fg="#567080",
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=7, pady=(0, 10))
        for label, icon, active in (("Command center", "âŒ˜", True), ("My notes", "â–¤", False), ("Timers", "â—·", False)):
            row = tk.Frame(self.sidebar, bg="#10202b" if active else SIDE, padx=10, pady=9)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=icon, bg=row["bg"], fg=CYAN if active else MUTED,
                     font=(FONT, 12), width=2).pack(side="left")
            tk.Label(row, text=label, bg=row["bg"], fg=INK if active else "#9cb0bb",
                     font=(FONT, 9, "bold" if active else "normal")).pack(side="left")
        spacer = tk.Frame(self.sidebar, bg=SIDE)
        spacer.pack(fill="both", expand=True)
        tk.Frame(self.sidebar, bg=LINE, height=1).pack(fill="x", pady=(0, 12))
        self._section_label(self.sidebar, "LOCAL SERVICES")
        self._service_row("â—", "Command engine", "READY", GREEN)
        self._service_row("â—", "Speech output", "OPTIONAL", AMBER)
        self._service_row("â—", "Speech input", "OPTIONAL", AMBER)
        tk.Label(self.sidebar, text="v1.0  Â·  RUNNING LOCALLY", bg=SIDE, fg="#526c79",
                 font=(FONT, 7, "bold")).pack(anchor="w", padx=7, pady=(20, 0))

    def _service_row(self, icon: str, title: str, status: str, color: str) -> None:
        row = tk.Frame(self.sidebar, bg=SIDE)
        row.pack(fill="x", padx=7, pady=5)
        tk.Label(row, text=icon, bg=SIDE, fg=color, font=(FONT, 8)).pack(side="left", padx=(0, 7))
        tk.Label(row, text=title, bg=SIDE, fg="#9aadb6", font=(FONT, 8)).pack(side="left")
        tk.Label(row, text=status, bg=SIDE, fg=color, font=(FONT, 6, "bold")).pack(side="right")

    def _build_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=BG)
        header.pack(fill="x", pady=(0, 18))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left")
        tk.Label(left, text="COMMAND CENTER", bg=BG, fg=CYAN_DIM,
                 font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(left, text="Good to see you, boss.", bg=BG, fg=INK,
                 font=(FONT, 20, "bold")).pack(anchor="w", pady=(3, 0))
        right = tk.Frame(header, bg=BG)
        right.pack(side="right", anchor="e")
        tk.Label(right, textvariable=self.clock_text, bg=BG, fg=INK,
                 font=(FONT, 15, "bold")).pack(anchor="e")
        tk.Label(right, textvariable=self.status_text, bg=BG, fg=GREEN,
                 font=(FONT, 7, "bold")).pack(anchor="e", pady=(3, 0))

    def _build_main(self, parent: tk.Widget) -> None:
        self._build_overview(parent)
        content = tk.Frame(parent, bg=BG)
        content.pack(fill="both", expand=True, pady=(15, 0))
        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))
        right = tk.Frame(content, bg=BG, width=250)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self._build_console(left)
        self._build_quick_actions(left)
        self._build_notes(right)

    def _build_overview(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x")
        self.cpu_value = self._metric_card(row, "PROCESSOR", "â€”", "CPU load")
        self.ram_value = self._metric_card(row, "MEMORY", "â€”", "RAM usage")
        self.os_value = self._metric_card(row, "PLATFORM", platform.system() or "LOCAL", platform.release()[:18])
        self.uptime_value = self._metric_card(row, "SESSION", "00:00", "since launch")
        self.started = time.monotonic()

    def _metric_card(self, parent: tk.Widget, title: str, value: str, caption: str) -> tk.Label:
        card = tk.Frame(parent, bg=PANEL, padx=13, pady=11, highlightthickness=1, highlightbackground=LINE)
        card.pack(side="left", fill="both", expand=True, padx=(0, 9))
        tk.Label(card, text=title, bg=PANEL, fg="#718a98", font=(FONT, 7, "bold")).pack(anchor="w")
        val = tk.Label(card, text=value, bg=PANEL, fg=CYAN, font=(FONT, 17, "bold"))
        val.pack(anchor="w", pady=(5, 1))
        tk.Label(card, text=caption, bg=PANEL, fg=MUTED, font=(FONT, 7)).pack(anchor="w")
        return val

    def _section_label(self, parent: tk.Widget, text: str) -> None:
        tk.Label(parent, text=text, bg=parent["bg"], fg="#718a98", font=(FONT, 8, "bold")).pack(anchor="w", pady=(0, 7))

    def _panel(self, parent: tk.Widget, title: str, eyebrow: str | None = None) -> tk.Frame:
        box = tk.Frame(parent, bg=PANEL, padx=14, pady=12, highlightthickness=1, highlightbackground=LINE)
        if eyebrow:
            tk.Label(box, text=eyebrow, bg=PANEL, fg=CYAN_DIM, font=(FONT, 7, "bold")).pack(anchor="w")
        tk.Label(box, text=title, bg=PANEL, fg=INK, font=(FONT, 11, "bold")).pack(anchor="w", pady=(3, 9))
        return box

    def _build_console(self, parent: tk.Widget) -> None:
        console = self._panel(parent, "Talk to me.", "READY WHEN YOU ARE")
        console.pack(fill="both", expand=True)
        bar = tk.Frame(console, bg=PANEL)
        bar.pack(fill="x", pady=(0, 9))
        tk.Label(bar, text="â—", bg=PANEL, fg=GREEN, font=(FONT, 8)).pack(side="left", padx=(0, 6))
        tk.Label(bar, textvariable=self.listen_text, bg=PANEL, fg=MUTED, font=(FONT, 7, "bold")).pack(side="left")
        self.log = tk.Text(console, bg="#0b141d", fg="#c1d5dd", insertbackground=CYAN,
                           relief="flat", wrap="word", font=("Consolas", 9), padx=11, pady=10,
                           height=12, spacing1=3, spacing3=4, state="disabled")
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("system", foreground=CYAN, font=("Consolas", 9, "bold"))
        self.log.tag_configure("user", foreground="#e7c27a")
        self.log.tag_configure("muted", foreground="#738a97", font=("Consolas", 8))
        self._log("J.A.R.V.I.S. ONLINE", "system")
        self._log("At your service. Try â€˜helpâ€™ to see what I can do.", "normal")
        self._log("Voice recognition sends microphone audio to Google for transcription.", "muted")
        input_row = tk.Frame(console, bg=PANEL)
        input_row.pack(fill="x", pady=(10, 0))
        self.command_entry = tk.Entry(input_row, textvariable=self.command, bg="#0b141d", fg=INK,
                                      insertbackground=CYAN, relief="flat", font=(FONT, 10),
                                      highlightthickness=1, highlightbackground=LINE, highlightcolor=CYAN)
        self.command_entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 7))
        self.command_entry.bind("<Return>", lambda _e: self.submit())
        self.command_entry.insert(0, "Type a commandâ€¦ try â€˜timeâ€™ or â€˜note call the dentistâ€™")
        self.command_entry.configure(fg="#647b88")
        self.command_entry.bind("<FocusIn>", self._clear_placeholder)
        self.command_entry.bind("<FocusOut>", self._restore_placeholder)
        self._button(input_row, "SEND  â†—", self.submit, accent=True, padx=12).pack(side="right")
        voice_row = tk.Frame(console, bg=PANEL)
        voice_row.pack(fill="x", pady=(8, 0))
        self._button(voice_row, "â—‰  Push to talk", self.listen, accent=False).pack(side="left")
        tk.Label(voice_row, text="Optional: install voice packages, then allow mic access.", bg=PANEL,
                 fg="#6f8490", font=(FONT, 7)).pack(side="left", padx=10)

    def _build_quick_actions(self, parent: tk.Widget) -> None:
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", pady=(12, 0))
        self._section_label(frame, "QUICK ACTIONS")
        actions = tk.Frame(frame, bg=BG)
        actions.pack(fill="x")
        for label, command in (("â—·  5 min timer", lambda: self.handle("timer 5 minutes")),
                               ("âŒ•  Search web", lambda: self._focus_with("search ")),
                               ("â–¤  New note", lambda: self._focus_with("note ")),
                               ("â–£  System report", lambda: self.handle("system status"))):
            self._button(actions, label, command).pack(side="left", padx=(0, 7))

    def _build_notes(self, parent: tk.Widget) -> None:
        box = self._panel(parent, "Notes", "YOUR LOCAL SCRATCHPAD")
        box.pack(fill="both", expand=True)
        self.note_count = tk.Label(box, text="0 saved", bg=PANEL, fg=MUTED, font=(FONT, 8))
        self.note_count.pack(anchor="w", pady=(0, 7))
        self.note_list = tk.Listbox(box, bg="#0b141d", fg="#c1d5dd", selectbackground="#193949",
                                    selectforeground=INK, relief="flat", borderwidth=0,
                                    font=(FONT, 8), highlightthickness=0, activestyle="none")
        self.note_list.pack(fill="both", expand=True, pady=(0, 9))
        self._button(box, "+  Add a note", lambda: self._focus_with("note "), accent=False).pack(fill="x")
        tk.Label(box, text="Notes stay on this computer.", bg=PANEL, fg="#657c88",
                 font=(FONT, 7)).pack(anchor="w", pady=(10, 0))

    def _button(self, parent: tk.Widget, text: str, command, accent: bool = False, padx: int = 10) -> tk.Button:
        bg = "#17404d" if accent else "#13212c"
        fg = CYAN if accent else "#a9bdc6"
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground="#205767", activeforeground=INK, relief="flat", bd=0,
                         cursor="hand2", padx=padx, pady=8, font=(FONT, 8, "bold" if accent else "normal"))

    def _log(self, text: str, tag: str = "normal") -> None:
        if not hasattr(self, "log"):
            return
        self.log.configure(state="normal")
        prefix = "" if tag == "muted" else ("YOU   â€º  " if tag == "user" else "JARVIS â€º  " if tag == "normal" else "")
        self.log.insert(END, prefix + text + "\n", tag)
        self.log.see(END)
        self.log.configure(state="disabled")

    def _clear_placeholder(self, _event=None) -> None:
        if self.command.get().startswith("Type a command"):
            self.command.set("")
            self.command_entry.configure(fg=INK)

    def _restore_placeholder(self, _event=None) -> None:
        if not self.command.get().strip():
            self.command.set("Type a commandâ€¦ try â€˜timeâ€™ or â€˜note call the dentistâ€™")
            self.command_entry.configure(fg="#647b88")

    def _focus_with(self, prefix: str) -> None:
        self.command.set(prefix)
        self.command_entry.configure(fg=INK)
        self.command_entry.focus_set()
        self.command_entry.icursor(END)

    def submit(self) -> None:
        text = self.command.get().strip()
        if not text or text.startswith("Type a command"):
            return
        self.command.set("")
        self.command_entry.configure(fg=INK)
        self._log(text, "user")
        self.handle(text)

    def handle(self, raw: str) -> None:
        text = raw.strip()
        low = text.lower()
        if low in ("hi", "hello", "hey", "hey jarvis", "hello jarvis"):
            self.respond("Hello. What can I help you with?")
        elif low in ("help", "commands", "what can you do"):
            self.respond("Try: time Â· date Â· system status Â· note <text> Â· show notes Â· timer 5 minutes Â· cancel timer Â· open calculator Â· open notepad Â· open YouTube Â· search <words>.")
        elif low in ("time", "what time is it", "tell me the time"):
            self.respond(f"It is {datetime.now().strftime('%I:%M %p').lstrip('0')}.")
        elif low in ("date", "what is the date", "what's the date", "what day is it"):
            self.respond(datetime.now().strftime("Today is %A, %B %d, %Y."))
        elif low in ("status", "system status", "system report", "how is the system"):
            self.respond(self._system_report())
        elif low.startswith("note ") or low.startswith("take a note ") or low.startswith("remember "):
            content = re.sub(r"^(note|take a note|remember)\s+", "", text, flags=re.I).strip()
            self._add_note(content)
        elif low in ("show notes", "list notes", "read my notes"):
            if self.notes:
                self.respond("Here are your recent notes: " + "; ".join(n["text"] for n in self.notes[-5:]))
            else:
                self.respond("You do not have any notes yet.")
        elif low.startswith("timer ") or low.startswith("set a timer "):
            self._start_timer(text)
        elif low in ("cancel timer", "stop timer", "cancel the timer"):
            self._cancel_timer()
        elif low.startswith("search "):
            query = text[7:].strip()
            if query:
                webbrowser.open("https://www.google.com/search?q=" + __import__("urllib.parse", fromlist=["quote_plus"]).quote_plus(query))
                self.respond(f"Searching the web for {query}.")
            else:
                self.respond("Tell me what you want to search for.")
        elif low.startswith("open "):
            self._open_target(text[5:].strip())
        elif low.startswith("say "):
            self.respond(text[4:].strip() or "I am listening.")
        else:
            self.respond("I do not know that command yet. Say â€˜helpâ€™ to see what I can do.")

    def respond(self, text: str) -> None:
        self._log(text)
        if self.speech_available:
            self.speech_queue.put(text)

    def _add_note(self, content: str) -> None:
        if not content:
            self.respond("What would you like me to write down?")
            return
        self.notes.append({"text": content, "created": datetime.now().isoformat(timespec="minutes")})
        try:
            NOTES_PATH.write_text(json.dumps(self.notes, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as error:
            self.respond(f"I could not save that note: {error}")
            return
        self._render_notes()
        self.respond("Noted. I saved that on this computer.")

    def _render_notes(self) -> None:
        if not hasattr(self, "note_list"):
            return
        self.note_list.delete(0, END)
        for item in reversed(self.notes[-20:]):
            summary = str(item["text"]).replace("\n", " ")
            self.note_list.insert(END, summary[:58] + ("â€¦" if len(summary) > 58 else ""))
        self.note_count.configure(text=f"{len(self.notes)} saved")

    def _start_timer(self, raw: str) -> None:
        match = re.search(r"(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)", raw, re.I)
        if not match:
            self.respond("Try a timer like â€˜timer 5 minutesâ€™ or â€˜timer 30 secondsâ€™.")
            return
        amount = int(match.group(1))
        unit = match.group(2).lower()
        factor = 3600 if unit.startswith(("hour", "hr")) else 60 if unit.startswith(("minute", "min")) else 1
        total = amount * factor
        if not 1 <= total <= 86400:
            self.respond("Choose a timer from one second up to 24 hours.")
            return
        timer_id = self.after(total * 1000, lambda: self._timer_finished(timer_id))
        self.active_timers[timer_id] = f"{amount} {unit}"
        self.respond(f"Timer started for {amount} {unit}.")

    def _timer_finished(self, timer_id: int) -> None:
        if self.active_timers.pop(timer_id, None) is not None:
            self.status_text.set("TIMER COMPLETE Â· CHECK IN")
            self.respond("Your timer is up.")
            self.after(6000, lambda: self.status_text.set("ALL SYSTEMS NOMINAL"))

    def _cancel_timer(self) -> None:
        if not self.active_timers:
            self.respond("There are no active timers.")
            return
        timer_id = next(reversed(self.active_timers))
        label = self.active_timers.pop(timer_id)
        self.after_cancel(timer_id)
        self.respond(f"Cancelled the {label} timer.")

    def _open_target(self, target: str) -> None:
        key = target.lower().strip()
        urls = {"youtube": "https://www.youtube.com", "google": "https://www.google.com",
                "github": "https://github.com", "gmail": "https://mail.google.com",
                "calendar": "https://calendar.google.com", "chatgpt": "https://chatgpt.com"}
        try:
            if key in urls:
                webbrowser.open(urls[key])
                self.respond(f"Opening {key} in your browser.")
            elif key in ("calculator", "calc"):
                if platform.system() == "Windows":
                    subprocess.Popen(["calc.exe"], shell=False)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", "-a", "Calculator"], shell=False)
                else:
                    subprocess.Popen(["gnome-calculator"], shell=False)
                self.respond("Opening calculator.")
            elif key in ("notepad", "text editor"):
                if platform.system() == "Windows":
                    subprocess.Popen(["notepad.exe"], shell=False)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", "-a", "TextEdit"], shell=False)
                else:
                    subprocess.Popen(["gedit"], shell=False)
                self.respond("Opening your text editor.")
            elif key in ("settings", "system settings") and platform.system() == "Windows":
                os.startfile("ms-settings:")  # type: ignore[attr-defined]
                self.respond("Opening system settings.")
            else:
                self.respond("I can open YouTube, Google, GitHub, Gmail, Calendar, ChatGPT, Calculator, or Notepad.")
        except (OSError, FileNotFoundError) as error:
            self.respond(f"I could not open that here: {error}")

    def _system_report(self) -> str:
        bits = [f"Operating system: {platform.system()} {platform.release()}."]
        try:
            import psutil  # type: ignore
            bits.append(f"Processor load is {psutil.cpu_percent(interval=None):.0f} percent.")
            bits.append(f"Memory usage is {psutil.virtual_memory().percent:.0f} percent.")
        except ImportError:
            bits.append("Install psutil to enable live processor and memory readings.")
        bits.append(f"You have {len(self.active_timers)} active timer{'s' if len(self.active_timers) != 1 else ''} and {len(self.notes)} saved notes.")
        return " ".join(bits)

    def _refresh_system(self) -> None:
        try:
            import psutil  # type: ignore
            self.cpu_value.configure(text=f"{psutil.cpu_percent(interval=None):.0f}%")
            self.ram_value.configure(text=f"{psutil.virtual_memory().percent:.0f}%")
        except ImportError:
            self.cpu_value.configure(text="OFF")
            self.ram_value.configure(text="OFF")
        minutes, seconds = divmod(int(time.monotonic() - self.started), 60)
        self.uptime_value.configure(text=f"{minutes:02d}:{seconds:02d}")
        self.after(2500, self._refresh_system)

    def _refresh_clock(self) -> None:
        now = datetime.now()
        self.clock_text.set(now.strftime("%I:%M:%S %p").lstrip("0") + "   Â·   " + now.strftime("%a, %b %d"))
        self.after(1000, self._refresh_clock)

    def listen(self) -> None:
        if not self.speech_available:
            self.listen_text.set("VOICE PACKAGES NOT INSTALLED")
            self.respond("Voice input is optional. Install the packages from requirements.txt, then restart me. Text commands are ready now.")
            return
        self.listen_text.set("LISTENING Â· SAY A COMMAND")
        self.status_text.set("MICROPHONE ACTIVE")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self) -> None:
        try:
            import speech_recognition as sr  # type: ignore
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=.35)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
            heard = recognizer.recognize_google(audio)
            self.after(0, lambda: self._heard_command(heard))
        except Exception as error:
            detail = "I could not hear a command. Check the microphone and try again."
            if error.__class__.__name__ in ("WaitTimeoutError", "UnknownValueError"):
                detail = "I did not catch that. Press to talk and try again."
            elif error.__class__.__name__ == "RequestError":
                detail = "Speech recognition could not connect. Check your internet connection."
            self.after(0, lambda: self._listen_failed(detail))

    def _heard_command(self, text: str) -> None:
        self.listen_text.set("VOICE INPUT READY")
        self.status_text.set("ALL SYSTEMS NOMINAL")
        self._log(text, "user")
        self.handle(text)

    def _listen_failed(self, detail: str) -> None:
        self.listen_text.set("VOICE INPUT READY")
        self.status_text.set("ALL SYSTEMS NOMINAL")
        self.respond(detail)

    def _speech_worker(self) -> None:
        try:
            import pyttsx3  # type: ignore
            engine = pyttsx3.init()
            engine.setProperty("rate", 180)
            self.speech_available = True
        except Exception:
            return
        while True:
            message = self.speech_queue.get()
            if message is None:
                break
            try:
                engine.say(message)
                engine.runAndWait()
            except Exception:
                pass

    def _close(self) -> None:
        for timer_id in list(self.active_timers):
            try:
                self.after_cancel(timer_id)
            except tk.TclError:
                pass
        self.speech_queue.put(None)
        self.destroy()


if __name__ == "__main__":
    Jarvis().mainloop()

