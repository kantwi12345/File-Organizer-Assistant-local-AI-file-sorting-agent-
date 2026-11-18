import json
import os
import shutil
import sys
import tkinter as tk
import winreg
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

from anthropic import Anthropic

ENVIRONMENT_ID = "env_016iJCziY3VCYPBiKHeofBT5"   # cloud environment from claude-lock.json
AGENT_ID = "agent_01Tomt6rZtzUnARvbGFxN25L"     # your agent ID, starts with agent_

client = Anthropic()

SYSTEM = (
    "You are a file organization assistant. You work in one folder on the user's PC, "
    "through two tools. All paths are relative to that folder. First call list_files "
    "(and list subfolders if needed) and propose a clear folder structure, such as by "
    "file type, project or date. Summarize the plan briefly. Then call move_files in "
    "batches of up to 50 moves; the user approves each batch. Never delete anything. "
    "Existing files are never overwritten. Skip hidden and system files. When finished, "
    "report what was moved where and anything you skipped."
)

TOOLS = [
    {
        "type": "custom",
        "name": "list_files",
        "description": "List files and folders inside the chosen folder. 'path' is relative "
                       "to it (default '.'). Returns type, path, size and modified date.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
    {
        "type": "custom",
        "name": "move_files",
        "description": "Move files into destination folders, which are created if missing. "
                       "All paths are relative to the chosen folder. The user approves each "
                       "batch. Existing files are never overwritten; name clashes get a "
                       "numeric suffix. Send at most 50 moves per call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "moves": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "src": {"type": "string"},
                            "dest_folder": {"type": "string"},
                        },
                        "required": ["src", "dest_folder"],
                    },
                }
            },
            "required": ["moves"],
        },
    },
]

# ---- Create the agent if there is no ID yet ----
if not AGENT_ID or AGENT_ID.startswith("PASTE"):
    agent = client.beta.agents.create(
        name="File Organizer (local)",
        model="claude-sonnet-5-5",
        system=SYSTEM,
        tools=TOOLS,
    )
    print(f"Created agent: {agent.id}")
    print("Paste it into AGENT_ID at the top of this file, then run the script again.")
    raise SystemExit


# ---- Folder selection ----
KNOWN = {
    "1": ("Downloads", "{374DE290-123F-4565-9164-39C4925E467B}"),
    "2": ("Desktop", "Desktop"),
    "3": ("Documents", "Personal"),
    "4": ("Pictures", "My Pictures"),
}


def known_folder(name, reg_value):
    # Reads where Windows actually keeps the folder, so it also works
    # when Desktop or Documents are moved into OneDrive.
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as k:
            value, _ = winreg.QueryValueEx(k, reg_value)
        return os.path.expandvars(value)
    except OSError:
        return str(Path.home() / name)


def pick_folder():
    win = tk.Tk()
    win.withdraw()
    win.attributes("-topmost", True)
    chosen = filedialog.askdirectory(title="Choose the folder to organize")
    win.destroy()
    return chosen


def choose_folder():
    print("Which folder do you want to organize?")
    for key, (name, reg) in KNOWN.items():
        print(f"  {key}. {name}  ({known_folder(name, reg)})")
    print("  5. Another folder (browse)")
    while True:
        choice = input("Enter a number: ").strip()
        if choice in KNOWN:
            name, reg = KNOWN[choice]
            return known_folder(name, reg)
        if choice == "5":
            return pick_folder()
        print("Type a number from 1 to 5.")


raw = sys.argv[1] if len(sys.argv) > 1 else choose_folder()
if not raw:
    raise SystemExit("No folder chosen.")

ROOT = Path(raw.strip().strip('"')).resolve()
if not ROOT.is_dir():
    raise SystemExit(f"Not a folder: {ROOT}")
if len(ROOT.parts) < 3 or any(
    p in {"Windows", "Program Files", "Program Files (x86)"} for p in ROOT.parts
):
    raise SystemExit("Pick a more specific folder, not a drive root or system folder.")

LOG = ROOT / "organizer_moves.jsonl"


def safe(rel):
    p = (ROOT / rel).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ValueError(f"Path is outside the chosen folder: {rel}")
    return p


def skip(p):
    return p.name.startswith(".") or p.name.lower() in {"desktop.ini", "thumbs.db"} or p == LOG


def unique(dest):
    if not dest.exists():
        return dest
    n = 1
    while True:
        cand = dest.with_name(f"{dest.stem} ({n}){dest.suffix}")
        if not cand.exists():
            return cand
        n += 1


# ---- Tool handlers (these run on your PC) ----
def list_files(inp):
    folder = safe(inp.get("path") or ".")
    if not folder.is_dir():
        return "Not a folder."
    rows = []
    for p in sorted(folder.iterdir()):
        if skip(p):
            continue
        st = p.stat()
        kind = "dir" if p.is_dir() else "file"
        rows.append(
            f"{kind} | {p.relative_to(ROOT)} | {st.st_size} bytes | "
            f"{datetime.fromtimestamp(st.st_mtime):%Y-%m-%d}"
        )
    return "\n".join(rows[:500]) or "(empty folder)"


def move_files(inp):
    moves = inp.get("moves") or []
    if not moves:
        return "No moves given."
    plan = []
    for m in moves:
        src = safe(m["src"])
        dest_dir = safe(m["dest_folder"])
        if skip(src) or not src.is_file():
            return f"Not a movable file: {m['src']}"
        plan.append((src, dest_dir))

    print(f"\n\nThe agent wants to move {len(plan)} files:")
    for src, d in plan[:40]:
        print(f"  {src.relative_to(ROOT)}  ->  {d.relative_to(ROOT)}")
    if len(plan) > 40:
        print(f"  ... and {len(plan) - 40} more")
    if input("Apply these moves? [y/N] ").strip().lower() != "y":
        return "The user declined these moves. Nothing was moved."

    with LOG.open("a", encoding="utf-8") as log:
        for src, d in plan:
            d.mkdir(parents=True, exist_ok=True)
            target = unique(d / src.name)
            shutil.move(str(src), str(target))
            log.write(json.dumps({"from": str(src), "to": str(target)}) + "\n")
    return f"Moved {len(plan)} files."


HANDLERS = {"list_files": list_files, "move_files": move_files}


def undo():
    if not LOG.exists():
        print("Nothing to undo.")
        return
    restored = skipped = 0
    for line in reversed(LOG.read_text(encoding="utf-8").splitlines()):
        r = json.loads(line)
        to, frm = Path(r["to"]), Path(r["from"])
        if to.exists() and not frm.exists():
            frm.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(to), str(frm))
            restored += 1
        else:
            skipped += 1
    LOG.unlink()
    print(f"Restored {restored} files, skipped {skipped}. Empty folders are left in place.")
    print("Restart the script before asking the agent anything else.")


# ---- Chat loop ----
session = client.beta.sessions.create(
    agent=AGENT_ID,
    environment_id=ENVIRONMENT_ID,
    title="File organizer (local)",
)
print(f"\nWorking in: {ROOT}")
print("Type 'undo' to reverse all moves, 'exit' to quit.")

while True:
    prompt = input("\nYou: ").strip()
    if not prompt:
        continue
    if prompt.lower() in {"exit", "quit"}:
        break
    if prompt.lower() == "undo":
        undo()
        continue

    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{
                "type": "user.message",
                "content": [{"type": "text", "text": prompt}],
            }],
        )
        for event in stream:
            match event.type:
                case "agent.message":
                    for block in event.content:
                        if block.type == "text":
                            print(block.text, end="")
                case "agent.custom_tool_use":
                    try:
                        out = HANDLERS[event.name](event.input)
                    except Exception as e:
                        out = f"Error: {e}"
                    client.beta.sessions.events.send(
                        session.id,
                        events=[{
                            "type": "user.custom_tool_result",
                            "custom_tool_use_id": event.id,
                            "content": [{"type": "text", "text": out or "(no output)"}],
                        }],
                    )
                case "session.status_idle":
                    stop = getattr(event, "stop_reason", None)
                    if getattr(stop, "type", None) == "requires_action":
                        continue
                    print("\n")
                    break
