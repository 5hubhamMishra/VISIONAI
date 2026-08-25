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
