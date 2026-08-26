# Environment Setup

VisionAI targets Python 3.12 on Windows. Python 3.12.10 is installed for this workspace, and the working local environment is `.venv312`.

## Repair Steps

1. Install Python 3.12 from python.org or another trusted source.
2. During installation, enable `Add python.exe to PATH`.
3. Open a new terminal and verify:

```powershell
python --version
```

4. Recreate the virtual environment from the `visionai` directory. If `.venv` is locked or broken, use `.venv312`:

```powershell
python -m venv .venv312
.\.venv312\Scripts\python -m pip install --upgrade pip
.\.venv312\Scripts\python -m pip install -r requirements\dev.txt
```

5. Run verification:

```powershell
.\scripts\verify.ps1
```

## Current Blocker

The existing `.venv\Scripts\python.exe` reports that it cannot find:

```text
C:\Users\shubh\AppData\Local\Programs\Python\Python312\python.exe
```

The current verified environment is `.venv312`. The older `.venv` directory may remain partially locked and should not be used.

## Known Issue: OneDrive Sync Can Corrupt the Virtual Environment

This workspace lives inside a OneDrive-synced folder
(`...\OneDrive\Desktop\DESKTOP\projects\demo\visionai`). OneDrive's
background sync can lock, move, or partially write files while `pip`
is rapidly creating or rewriting files during `python -m venv` or
`pip install`, corrupting the environment mid-write. This is a
plausible explanation for the blocker above, and was confirmed twice
directly on this machine with a different symptom:

- `pip` itself became unusable (`ModuleNotFoundError: No module named
  pip._vendor.rich`, then later `No module named pip`) immediately
  after an install that had printed a transient `OSError` mid-run,
  with no unrelated cause found.

If a virtual environment inside this folder becomes unusable, don't
keep retrying in place -- delete the broken `.venv*` folder and
recreate it, and while doing so either:

- Pause OneDrive sync (right-click the OneDrive tray icon > Pause
  syncing) until `pip install` finishes, or
- Create the virtual environment somewhere outside the OneDrive tree
  (for example `%TEMP%\visionai-venv`) and point `scripts\verify.ps1`
  or your shell at that path instead of a local `.venv*` folder.
