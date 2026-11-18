# File Organizer Assistant

An AI agent that sorts files into folders. It is built as a Claude Managed Agent and runs locally on Windows through a Python script, `organizer_local.py`.

## What it does

The agent reads the files in a target folder and moves them into organized subfolders. [Describe the sorting logic here: by file type, by name, by content, or a mix.]

## Project contents

```
FileOrganizer/
├── organizer_local.py     # Local runner for the agent
├── <agent file>           # Agent definition
├── <environment file>     # Agent environment definition
├── claude-lock.json       # Lock file for the agent package
└── venv/                  # Python virtual environment
```

Replace the bracketed file names with the actual names from the agent zip.

## Requirements

- Windows
- Python 3.9 or newer
- An Anthropic API key
- The packages listed in `requirements.txt` [add this file if it does not exist: `pip freeze > requirements.txt`]

## Setup

```
cd C:\Users\Hulede\FileOrganizer
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set ANTHROPIC_API_KEY=your-key-here
```

Do not commit the API key. Keep it in an environment variable or a `.env` file listed in `.gitignore`.

## Usage

Point the script at a folder:

```
python organizer_local.py "C:\Users\Hulede\OrganizeTest"
```

[Confirm the actual argument. If the script takes no argument and reads a hardcoded path, say so here.]

## Testing

Run it on a copy of your files first. The script was tested on `C:\Users\Hulede\OrganizeTest` before use on real folders.

## Limitations

- Runs on Windows paths only.
- [List any file types it skips or any folders it never touches.]
- [Note whether it can undo a move.]

## Files that need your input

Three parts of this README need details only you have: the sorting logic, the exact command-line usage, and the limitations. Fill those in before you publish it.
