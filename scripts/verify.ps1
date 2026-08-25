param(
    [switch]$SkipAudit
)

$ErrorActionPreference = "Stop"

if (Test-Path -LiteralPath ".venv312\Scripts\python.exe") {
    $Python = ".venv312\Scripts\python.exe"
} elseif (Test-Path -LiteralPath ".venv\Scripts\python.exe") {
    $Python = ".venv\Scripts\python.exe"
} else {
    $Python = "python"
}

function Invoke-Checked {
    param([string[]]$Command)
    & $Command[0] @($Command[1..($Command.Length - 1)])
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $($Command -join ' ')"
    }
}

Invoke-Checked @($Python, "-m", "ruff", "check", ".")
Invoke-Checked @($Python, "-m", "mypy", "src")
Invoke-Checked @($Python, "-m", "pytest", "--cov=src/visionai", "--cov-report=term-missing")

if (-not $SkipAudit) {
    Invoke-Checked @($Python, "-m", "bandit", "-q", "-r", "src")
    Invoke-Checked @($Python, "-m", "pip_audit", "-r", "requirements/base.txt", "-r", "requirements/dev.txt")
}
