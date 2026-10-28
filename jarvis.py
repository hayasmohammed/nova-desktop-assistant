"""NOVA â€” a local desktop assistant with a voice-ready command console.

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
from urllib.parse import quote_plus
from tkinter import END, StringVar, Tk, messagebox
from tkinter import ttk
import tkinter as tk


ROOT = Path(__file__).resolve().parent
NOTES_PATH = ROOT / "nova_notes.json"
LEGACY_NOTES_PATH = ROOT / "jarvis_notes.json"
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
        source = NOTES_PATH if NOTES_PATH.exists() else LEGACY_NOTES_PATH
        value = json.loads(source.read_text(encoding="utf-8"))
        return [x for x in value if isinstance(x, dict) and x.get("text")] if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


class Nova(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NOVA â€” Personal Desktop Assistant")
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
        self.microphone_available = False
        self.listening = False
        self.speech_enabled = True
        self.active_timers: dict[int, dict] = {}
        self.timer_serial = 0
        self.timer_update_job = None
        self.activity: list[dict[str, str]] = []
        self.command_history: list[str] = []
        self.history_cursor = 0
        self.current_view = "home"
        self._setup_style()
        self._build()
        self.bind("<Control-l>", lambda _e: self._focus_with(""))
        self._refresh_clock()
        self._refresh_system()
        self._render_notes()
        threading.Thread(target=self._speech_worker, daemon=True).start()
        threading.Thread(target=self._voice_package_check_worker, daemon=True).start()
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
        tk.Label(brand, text="NOVA", bg=SIDE, fg=INK,
                 font=(FONT, 13, "bold")).pack(side="left")
        tk.Label(self.sidebar, text="PERSONAL SYSTEM", bg=SIDE, fg="#567080",
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=7, pady=(0, 10))
        self.nav_buttons = {}
        for key, label, icon in (("home", "Command center", "âŒ˜"), ("notes", "My notes", "â–¤"),
                                 ("timers", "Timers", "â—·"), ("activity", "Activity log", "â‰‹"),
                                 ("settings", "Settings", "âš™")):
            button = tk.Button(self.sidebar, text=f"{icon}   {label}", anchor="w", command=lambda k=key: self._show_view(k),
                               bg=SIDE, fg="#9cb0bb", activebackground="#10202b", activeforeground=INK,
                               relief="flat", bd=0, cursor="hand2", padx=10, pady=10,
                               font=(FONT, 9), highlightthickness=0)
            button.pack(fill="x", pady=2)
            self.nav_buttons[key] = button
        spacer = tk.Frame(self.sidebar, bg=SIDE)
        spacer.pack(fill="both", expand=True)
        tk.Frame(self.sidebar, bg=LINE, height=1).pack(fill="x", pady=(0, 12))
        self._section_label(self.sidebar, "LOCAL SERVICES")
        self._service_row("â—", "Command engine", "READY", GREEN)
        self.speech_service = self._service_row("â—", "Speech output", "CHECKING", AMBER)
        self.mic_service = self._service_row("â—", "Speech input", "OPTIONAL", AMBER)
        tk.Label(self.sidebar, text="v1.1  Â·  RUNNING LOCALLY", bg=SIDE, fg="#526c79",
                 font=(FONT, 7, "bold")).pack(anchor="w", padx=7, pady=(20, 0))

    def _service_row(self, icon: str, title: str, status: str, color: str) -> tk.Label:
        row = tk.Frame(self.sidebar, bg=SIDE)
        row.pack(fill="x", padx=7, pady=5)
        tk.Label(row, text=icon, bg=SIDE, fg=color, font=(FONT, 8)).pack(side="left", padx=(0, 7))
        tk.Label(row, text=title, bg=SIDE, fg="#9aadb6", font=(FONT, 8)).pack(side="left")
        status_label = tk.Label(row, text=status, bg=SIDE, fg=color, font=(FONT, 6, "bold"))
        status_label.pack(side="right")
        return status_label

    def _build_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=BG)
        header.pack(fill="x", pady=(0, 18))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left")
        self.header_eyebrow = tk.Label(left, text="COMMAND CENTER", bg=BG, fg=CYAN_DIM,
                                       font=(FONT, 8, "bold"))
        self.header_eyebrow.pack(anchor="w")
        self.page_heading = tk.Label(left, text="Good to see you, boss.", bg=BG, fg=INK,
                                     font=(FONT, 20, "bold"))
        self.page_heading.pack(anchor="w", pady=(3, 0))
        right = tk.Frame(header, bg=BG)
        right.pack(side="right", anchor="e")
        tk.Label(right, textvariable=self.clock_text, bg=BG, fg=INK,
                 font=(FONT, 15, "bold")).pack(anchor="e")
        tk.Label(right, textvariable=self.status_text, bg=BG, fg=GREEN,
                 font=(FONT, 7, "bold")).pack(anchor="e", pady=(3, 0))

    def _build_main(self, parent: tk.Widget) -> None:
        self.view_area = tk.Frame(parent, bg=BG)
        self.view_area.pack(fill="both", expand=True, pady=(15, 0))
        self._show_view("home")

    def _show_view(self, key: str) -> None:
        if self.timer_update_job is not None:
            try:
                self.after_cancel(self.timer_update_job)
            except tk.TclError:
                pass
            self.timer_update_job = None
        self.current_view = key
        for child in self.view_area.winfo_children():
            child.destroy()
        labels = {"home": ("COMMAND CENTER", "Good to see you, boss."),
                  "notes": ("PERSONAL SCRATCHPAD", "Your notes."),
                  "timers": ("TIME MANAGEMENT", "Timers & reminders."),
                  "activity": ("RECENT COMMANDS", "Activity log."),
                  "settings": ("PREFERENCES", "Make it yours.")}
        eyebrow, title = labels[key]
        self.header_eyebrow.configure(text=eyebrow)
        self.page_heading.configure(text=title)
        for nav_key, button in self.nav_buttons.items():
            active = nav_key == key
            button.configure(bg="#10202b" if active else SIDE, fg=INK if active else "#9cb0bb",
                             font=(FONT, 9, "bold" if active else "normal"))
        if key == "home":
            self._build_dashboard(self.view_area)
        elif key == "notes":
            self._build_notes_page(self.view_area)
        elif key == "timers":
            self._build_timers_page(self.view_area)
        elif key == "activity":
            self._build_activity_page(self.view_area)
        else:
            self._build_settings_page(self.view_area)

    def _build_dashboard(self, parent: tk.Widget) -> None:
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
        self._log("NOVA ONLINE", "system")
        self._log("At your service. Try â€˜helpâ€™ to see what I can do.", "normal")
        self._log("Voice recognition sends microphone audio to Google for transcription.", "muted")
        input_row = tk.Frame(console, bg=PANEL)
        input_row.pack(fill="x", pady=(10, 0))
        self.command_entry = tk.Entry(input_row, textvariable=self.command, bg="#0b141d", fg=INK,
                                      insertbackground=CYAN, relief="flat", font=(FONT, 10),
                                      highlightthickness=1, highlightbackground=LINE, highlightcolor=CYAN)
        self.command_entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 7))
        self.command_entry.bind("<Return>", lambda _e: self.submit())
        self.command_entry.bind("<Up>", self._history_up)
        self.command_entry.bind("<Down>", self._history_down)
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
        self.note_list.bind("<Double-1>", lambda _e: self._edit_selected_note(self.note_list))
        self._button(box, "+  Add a note", lambda: self._edit_note(None), accent=False).pack(fill="x")
        note_actions = tk.Frame(box, bg=PANEL)
        note_actions.pack(fill="x", pady=(5, 0))
        self._button(note_actions, "Edit", lambda: self._edit_selected_note(self.note_list)).pack(side="left", fill="x", expand=True, padx=(0, 3))
        self._button(note_actions, "Delete", lambda: self._delete_selected_note(self.note_list)).pack(side="left", fill="x", expand=True, padx=(3, 0))
        tk.Label(box, text="Notes stay on this computer.", bg=PANEL, fg="#657c88",
                 font=(FONT, 7)).pack(anchor="w", pady=(10, 0))
        self._render_notes()

    def _build_notes_page(self, parent: tk.Widget) -> None:
        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", pady=(0, 12))
        tk.Label(toolbar, text="Write down ideas and reminders. Theyâ€™re stored on this device.",
                 bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")
        self._button(toolbar, "+  New note", lambda: self._edit_note(None), accent=True).pack(side="right")
        panel = self._panel(parent, "All notes", "LOCAL Â· PRIVATE")
        panel.pack(fill="both", expand=True)
        self.note_count = tk.Label(panel, text="0 saved", bg=PANEL, fg=MUTED, font=(FONT, 8))
        self.note_count.pack(anchor="w", pady=(0, 8))
        self.note_list = tk.Listbox(panel, bg="#0b141d", fg="#c1d5dd", selectbackground="#193949",
                                    selectforeground=INK, relief="flat", borderwidth=0,
                                    font=(FONT, 9), highlightthickness=0, activestyle="none")
        self.note_list.pack(fill="both", expand=True, pady=(0, 10))
        self.note_list.bind("<Double-1>", lambda _e: self._edit_selected_note(self.note_list))
        actions = tk.Frame(panel, bg=PANEL)
        actions.pack(fill="x")
        self._button(actions, "Edit selected", lambda: self._edit_selected_note(self.note_list)).pack(side="left", padx=(0, 6))
        self._button(actions, "Delete selected", lambda: self._delete_selected_note(self.note_list)).pack(side="left")
        self._render_notes()

    def _note_index(self, listbox: tk.Listbox) -> int | None:
        selection = listbox.curselection()
        if not selection:
            return None
        index = len(self.notes) - 1 - int(selection[0])
        return index if 0 <= index < len(self.notes) else None

    def _edit_selected_note(self, listbox: tk.Listbox) -> None:
        index = self._note_index(listbox)
        if index is None:
            self.respond("Select a note first.")
            return
        self._edit_note(index)

    def _edit_note(self, index: int | None) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("New note" if index is None else "Edit note")
        dialog.configure(bg=BG)
        dialog.geometry("460x330")
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(dialog, text="NEW NOTE" if index is None else "EDIT NOTE", bg=BG, fg=CYAN_DIM,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=18, pady=(16, 7))
        editor = tk.Text(dialog, bg="#0b141d", fg=INK, insertbackground=CYAN, wrap="word",
                         relief="flat", font=(FONT, 10), padx=11, pady=10)
        editor.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        if index is not None:
            editor.insert("1.0", self.notes[index]["text"])
        actions = tk.Frame(dialog, bg=BG)
        actions.pack(fill="x", padx=18, pady=(0, 16))

        def save_note() -> None:
            content = editor.get("1.0", "end-1c").strip()
            if not content:
                messagebox.showinfo("Empty note", "Add a little text before saving.", parent=dialog)
                return
            previous = self.notes[index].copy() if index is not None else None
            if index is None:
                self.notes.append({"text": content, "created": datetime.now().isoformat(timespec="minutes")})
            else:
                self.notes[index]["text"] = content
                self.notes[index]["updated"] = datetime.now().isoformat(timespec="minutes")
            if not self._save_notes():
                if index is None:
                    self.notes.pop()
                else:
                    self.notes[index] = previous
                return
            self._render_notes()
            self._log("Saved a note.", "system")
            dialog.destroy()

        self._button(actions, "Cancel", dialog.destroy).pack(side="right", padx=(6, 0))
        self._button(actions, "Save note", save_note, accent=True).pack(side="right")
        editor.focus_set()

    def _delete_selected_note(self, listbox: tk.Listbox) -> None:
        index = self._note_index(listbox)
        if index is None:
            self.respond("Select a note first.")
            return
        if not messagebox.askyesno("Delete note", "Delete this note from this computer?", parent=self):
            return
        deleted = self.notes.pop(index)
        if not self._save_notes():
            self.notes.insert(index, deleted)
            return
        self._render_notes()
        self._log("Deleted a note.", "system")

    def _save_notes(self) -> bool:
        try:
            NOTES_PATH.write_text(json.dumps(self.notes, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except OSError as error:
            messagebox.showerror("Could not save notes", str(error), parent=self)
            return False

    def _build_timers_page(self, parent: tk.Widget) -> None:
        intro = tk.Frame(parent, bg=BG)
        intro.pack(fill="x", pady=(0, 13))
        tk.Label(intro, text="Timers keep running while NOVA is open.", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(side="left")
        create = tk.Frame(parent, bg=PANEL, padx=14, pady=12, highlightthickness=1, highlightbackground=LINE)
        create.pack(fill="x", pady=(0, 12))
        tk.Label(create, text="START A TIMER", bg=PANEL, fg=CYAN_DIM, font=(FONT, 7, "bold")).pack(anchor="w")
        row = tk.Frame(create, bg=PANEL)
        row.pack(fill="x", pady=(8, 0))
        self.timer_entry = tk.Entry(row, bg="#0b141d", fg=INK, insertbackground=CYAN,
                                    relief="flat", font=(FONT, 10), highlightthickness=1,
                                    highlightbackground=LINE)
        self.timer_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.timer_entry.insert(0, "e.g. 5 minutes")
        self.timer_entry.bind("<FocusIn>", lambda _e: self._timer_placeholder(False))
        self.timer_entry.bind("<Return>", lambda _e: self._start_timer_from_field())
        self._button(row, "Start timer", self._start_timer_from_field, accent=True).pack(side="right")
        panel = self._panel(parent, "Active timers", "LIVE COUNTDOWN")
        panel.pack(fill="both", expand=True)
        self.timer_list = tk.Listbox(panel, bg="#0b141d", fg="#c1d5dd", selectbackground="#193949",
                                     selectforeground=INK, relief="flat", borderwidth=0,
                                     font=(FONT, 10), highlightthickness=0, activestyle="none")
        self.timer_list.pack(fill="both", expand=True, pady=(0, 10))
        actions = tk.Frame(panel, bg=PANEL)
        actions.pack(fill="x")
        self._button(actions, "Cancel selected", self._cancel_selected_timer).pack(side="left")
        self._button(actions, "Cancel latest", self._cancel_timer).pack(side="left", padx=6)
        self._render_timers()
        self._schedule_timer_refresh()

    def _timer_placeholder(self, restore: bool) -> None:
        if not hasattr(self, "timer_entry") or not self.timer_entry.winfo_exists():
            return
        if restore and not self.timer_entry.get().strip():
            self.timer_entry.insert(0, "e.g. 5 minutes")
            self.timer_entry.configure(fg="#647b88")
        elif not restore and self.timer_entry.get() == "e.g. 5 minutes":
            self.timer_entry.delete(0, END)
            self.timer_entry.configure(fg=INK)

    def _start_timer_from_field(self) -> None:
        value = self.timer_entry.get().strip()
        if value == "e.g. 5 minutes":
            value = ""
        started = self._start_timer("timer " + value)
        if started:
            self.timer_entry.delete(0, END)
            self._timer_placeholder(True)

    def _render_timers(self) -> None:
        if not hasattr(self, "timer_list") or not self.timer_list.winfo_exists():
            return
        selected = self.timer_list.curselection()
        timer_ids = list(self.active_timers)
        selected_id = timer_ids[int(selected[0])] if selected and int(selected[0]) < len(timer_ids) else None
        self.timer_list.delete(0, END)
        now = time.monotonic()
        for index, (timer_id, timer) in enumerate(self.active_timers.items()):
            remaining = max(0, int(timer["deadline"] - now + .999))
            minutes, seconds = divmod(remaining, 60)
            hours, minutes = divmod(minutes, 60)
            countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
            self.timer_list.insert(END, f"  {countdown}     {timer['label']}")
            if timer_id == selected_id:
                self.timer_list.selection_set(index)
        if not self.active_timers:
            self.timer_list.insert(END, "  No active timers. Start one above or say â€˜timer 5 minutesâ€™.")

    def _schedule_timer_refresh(self) -> None:
        if self.current_view == "timers":
            self._render_timers()
            self.timer_update_job = self.after(1000, self._schedule_timer_refresh)

    def _cancel_selected_timer(self) -> None:
        if not self.active_timers:
            self.respond("There are no active timers.")
            return
        selection = self.timer_list.curselection()
        if not selection or selection[0] >= len(self.active_timers):
            self.respond("Select an active timer first.")
            return
        timer_id = list(self.active_timers)[int(selection[0])]
        self._cancel_timer_id(timer_id)

    def _build_activity_page(self, parent: tk.Widget) -> None:
        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", pady=(0, 12))
        tk.Label(toolbar, text="Recent commands and actions from this session.", bg=BG, fg=MUTED,
                 font=(FONT, 9)).pack(side="left")
        self._button(toolbar, "Clear log", self._clear_activity).pack(side="right")
        panel = self._panel(parent, "Session activity", "KEPT IN MEMORY Â· CLEARED WHEN THE APP CLOSES")
        panel.pack(fill="both", expand=True)
        self.activity_list = tk.Listbox(panel, bg="#0b141d", fg="#c1d5dd", selectbackground="#193949",
                                        selectforeground=INK, relief="flat", borderwidth=0,
                                        font=("Consolas", 9), highlightthickness=0, activestyle="none")
        self.activity_list.pack(fill="both", expand=True)
        self._render_activity()

    def _render_activity(self) -> None:
        if not hasattr(self, "activity_list") or not self.activity_list.winfo_exists():
            return
        self.activity_list.delete(0, END)
        for item in self.activity[-250:]:
            self.activity_list.insert(END, f"  {item['time']}   {item['text']}")
        self.activity_list.see(END)

    def _clear_activity(self) -> None:
        if messagebox.askyesno("Clear activity", "Clear this sessionâ€™s activity log?", parent=self):
            self.activity.clear()
            self._render_activity()

    def _build_settings_page(self, parent: tk.Widget) -> None:
        grid = tk.Frame(parent, bg=BG)
        grid.pack(fill="both", expand=True)
        privacy = self._panel(grid, "Privacy & local data", "YOUR DEVICE")
        privacy.pack(fill="x", pady=(0, 12))
        tk.Label(privacy, text="Notes are saved in nova_notes.json beside the app. Activity stays in memory and clears when you close NOVA.\n\nVoice transcription uses Google Speech Recognition and sends recorded microphone audio for transcription. Spoken replies use pyttsx3 and your computerâ€™s installed voice.",
                 bg=PANEL, fg="#9cb0bb", justify="left", wraplength=650, font=(FONT, 9)).pack(anchor="w")
        voice = self._panel(grid, "Voice", "OPTIONAL FEATURES")
        voice.pack(fill="x", pady=(0, 12))
        self.voice_toggle = tk.BooleanVar(value=self.speech_enabled)
        tk.Checkbutton(voice, text="Speak NOVA replies aloud when speech output is installed",
                       variable=self.voice_toggle, command=self._toggle_speech,
                       bg=PANEL, fg=INK, selectcolor="#0b141d", activebackground=PANEL,
                       activeforeground=INK, font=(FONT, 9)).pack(anchor="w")
        self._button(voice, "Check voice packages", self._check_voice_packages).pack(anchor="w", pady=(9, 0))
        system = self._panel(grid, "System integrations", "AVAILABLE COMMANDS")
        system.pack(fill="x")
        tk.Label(system, text="App launching is limited to the named shortcuts in the command list. NOVA does not run arbitrary terminal commands. Add more fixed shortcuts in jarvis.py when you want to expand it.",
                 bg=PANEL, fg="#9cb0bb", justify="left", wraplength=650, font=(FONT, 9)).pack(anchor="w")

    def _toggle_speech(self) -> None:
        self.speech_enabled = self.voice_toggle.get()
        self.respond("Spoken replies enabled." if self.speech_enabled else "Spoken replies muted.")

    def _check_voice_packages(self) -> None:
        threading.Thread(target=self._voice_package_check_worker, daemon=True).start()

    def _voice_package_check_worker(self) -> None:
        try:
            import speech_recognition  # type: ignore # noqa: F401
            import pyaudio  # type: ignore # noqa: F401
            mic = True
        except Exception:
            mic = False
        try:
            import pyttsx3  # type: ignore # noqa: F401
            tts = True
        except Exception:
            tts = False
        self.microphone_available = mic
        self.speech_available = tts
        self.after(0, self._update_voice_status)

    def _update_voice_status(self) -> None:
        if not hasattr(self, "speech_service"):
            return
        self.speech_service.configure(text="READY" if self.speech_available else "NOT INSTALLED",
                                      fg=GREEN if self.speech_available else AMBER)
        self.mic_service.configure(text="READY" if self.microphone_available else "NOT INSTALLED",
                                   fg=GREEN if self.microphone_available else AMBER)
        self.listen_text.set("VOICE INPUT READY" if self.microphone_available else "TEXT COMMANDS READY")

    def _button(self, parent: tk.Widget, text: str, command, accent: bool = False, padx: int = 10) -> tk.Button:
        bg = "#17404d" if accent else "#13212c"
        fg = CYAN if accent else "#a9bdc6"
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground="#205767", activeforeground=INK, relief="flat", bd=0,
                         cursor="hand2", padx=padx, pady=8, font=(FONT, 8, "bold" if accent else "normal"))

    def _log(self, text: str, tag: str = "normal") -> None:
        if not hasattr(self, "log"):
            return
        if tag in ("normal", "user", "system"):
            self.activity.append({"time": datetime.now().strftime("%H:%M:%S"), "text": text})
            del self.activity[:-250]
        self.log.configure(state="normal")
        prefix = "" if tag == "muted" else ("YOU   â€º  " if tag == "user" else "NOVA  â€º  " if tag == "normal" else "")
        self.log.insert(END, prefix + text + "\n", tag)
        self.log.see(END)
        self.log.configure(state="disabled")
        if self.current_view == "activity":
            self._render_activity()

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
        self.command_history.append(text)
        self.history_cursor = len(self.command_history)
        self.command_entry.configure(fg=INK)
        self._log(text, "user")
        self.handle(text)

    def _history_up(self, _event=None):
        if self.command_history:
            self.history_cursor = max(0, self.history_cursor - 1)
            self.command.set(self.command_history[self.history_cursor])
            self.command_entry.configure(fg=INK)
            self.command_entry.icursor(END)
        return "break"

    def _history_down(self, _event=None):
        if self.command_history:
            self.history_cursor = min(len(self.command_history), self.history_cursor + 1)
            value = self.command_history[self.history_cursor] if self.history_cursor < len(self.command_history) else ""
            self.command.set(value)
            self.command_entry.configure(fg=INK)
            self.command_entry.icursor(END)
        return "break"

    def handle(self, raw: str) -> None:
        text = raw.strip()
        low = text.lower()
        if low in ("hi", "hello", "hey", "hey nova", "hello nova"):
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
                webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
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
        if self.speech_available and self.speech_enabled:
            self.speech_queue.put(text)

    def _add_note(self, content: str) -> None:
        if not content:
            self.respond("What would you like me to write down?")
            return
        self.notes.append({"text": content, "created": datetime.now().isoformat(timespec="minutes")})
        if not self._save_notes():
            self.notes.pop()
            return
        self._render_notes()
        self.respond("Noted. I saved that on this computer.")

    def _render_notes(self) -> None:
        if not hasattr(self, "note_list") or not self.note_list.winfo_exists():
            return
        self.note_list.delete(0, END)
        for item in reversed(self.notes[-20:]):
            summary = str(item["text"]).replace("\n", " ")
            self.note_list.insert(END, summary[:58] + ("â€¦" if len(summary) > 58 else ""))
        self.note_count.configure(text=f"{len(self.notes)} saved")

    def _start_timer(self, raw: str) -> bool:
        match = re.search(r"(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)", raw, re.I)
        if not match:
            self.respond("Try a timer like â€˜timer 5 minutesâ€™ or â€˜timer 30 secondsâ€™.")
            return False
        amount = int(match.group(1))
        unit = match.group(2).lower()
        factor = 3600 if unit.startswith(("hour", "hr")) else 60 if unit.startswith(("minute", "min")) else 1
        total = amount * factor
        if not 1 <= total <= 86400:
            self.respond("Choose a timer from one second up to 24 hours.")
            return False
        self.timer_serial += 1
        timer_id = self.timer_serial
        deadline = time.monotonic() + total
        after_id = self.after(total * 1000, lambda: self._timer_finished(timer_id))
        self.active_timers[timer_id] = {"label": f"{amount} {unit}", "deadline": deadline, "after_id": after_id}
        self._render_timers()
        self.respond(f"Timer started for {amount} {unit}.")
        return True

    def _timer_finished(self, timer_id: int) -> None:
        if self.active_timers.pop(timer_id, None) is not None:
            self._render_timers()
            self.status_text.set("TIMER COMPLETE Â· CHECK IN")
            self.bell()
            self.respond("Your timer is up.")
            self.after(6000, lambda: self.status_text.set("ALL SYSTEMS NOMINAL"))

    def _cancel_timer(self) -> None:
        if not self.active_timers:
            self.respond("There are no active timers.")
            return
        timer_id = next(reversed(self.active_timers))
        self._cancel_timer_id(timer_id)

    def _cancel_timer_id(self, timer_id: int) -> None:
        timer = self.active_timers.pop(timer_id, None)
        if timer is None:
            return
        try:
            self.after_cancel(timer["after_id"])
        except tk.TclError:
            pass
        self._render_timers()
        self.respond(f"Cancelled the {timer['label']} timer.")

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
        if self.listening:
            self.respond("Iâ€™m already listening. Finish your command or wait for the timeout.")
            return
        if not self.microphone_available:
            self.listen_text.set("VOICE INPUT NOT READY")
            self.respond("Voice input needs SpeechRecognition and PyAudio. Install the packages from requirements.txt, then use Check voice packages in Settings. Text commands are ready now.")
            return
        self.listen_text.set("LISTENING Â· SAY A COMMAND")
        self.status_text.set("MICROPHONE ACTIVE")
        self.listening = True
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
        self.listening = False
        self.listen_text.set("VOICE INPUT READY")
        self.status_text.set("ALL SYSTEMS NOMINAL")
        self.command_history.append(text)
        self.history_cursor = len(self.command_history)
        self._log(text, "user")
        self.handle(text)

    def _listen_failed(self, detail: str) -> None:
        self.listening = False
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
        for timer in list(self.active_timers.values()):
            try:
                self.after_cancel(timer["after_id"])
            except tk.TclError:
                pass
        if self.timer_update_job is not None:
            try:
                self.after_cancel(self.timer_update_job)
            except tk.TclError:
                pass
        self.speech_queue.put(None)
        self.destroy()


if __name__ == "__main__":
    Nova().mainloop()

