# set-core installer for Windows PowerShell
# Run as: .\install.ps1

$ErrorActionPreference = "Stop"

function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Blue }
function Write-Success { param($Message) Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Err { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = "$env:LOCALAPPDATA\set-core\bin"
$ConfigDir = "$env:APPDATA\set-core"

function Test-Command {
    param($Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Check-Prerequisites {
    Write-Info "Checking prerequisites..."

    $missing = @()

    if (-not (Test-Command "git")) {
        $missing += "git"
    }

    # Check for jq (needed for JSON parsing in bash scripts)
    if (-not (Test-Command "jq")) {
        $missing += "jq"
    }

    if ($missing.Count -gt 0) {
        Write-Err "Missing required tools: $($missing -join ', ')"
        Write-Host ""
        Write-Host "Install them first:"
        Write-Host "  winget install Git.Git"
        Write-Host "  winget install jqlang.jq"
        Write-Host "  # Or use Chocolatey: choco install git jq"
        exit 1
    }

    Write-Success "Prerequisites OK (git, jq)"

    # Check optional Python
    if (-not (Test-Command "python") -and -not (Test-Command "python3")) {
        Write-Warn "Python not found. GUI features will be unavailable."
        Write-Host "  Install with: winget install Python.Python.3.12"
    }
}

function Install-Scripts {
    Write-Info "Installing set-core scripts..."

    # Create install directory
    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    # For Windows, we recommend using Git Bash to run the scripts
    # Copy scripts to install location
    $scripts = @(
        "set-common.sh",
        "set-project",
        "set-new",
        "set-work",
        "set-list",
        "set-close",
        "set-merge",
        "set-status",
        "set-version",
        "set-focus",
        "set-control",
        "set-control-gui",
        "set-control-init",
        "set-control-sync",
        "set-control-chat",
        "set-loop"
    )

    foreach ($script in $scripts) {
        $src = Join-Path $ScriptDir "bin\$script"
        $dst = Join-Path $InstallDir $script

        if (Test-Path $src) {
            Copy-Item $src $dst -Force
            Write-Success "  Copied: $script"
        } else {
            Write-Warn "  Not found: $src"
        }
    }

    # Create wrapper batch files for easy calling from CMD/PowerShell
    $wrapperScripts = @(
        "set-project",
        "set-new",
        "set-work",
        "set-list",
        "set-close",
        "set-merge",
        "set-status",
        "set-version"
    )
    foreach ($script in $wrapperScripts) {
        $batFile = Join-Path $InstallDir "$script.cmd"
        $content = "@echo off`nbash `"%~dp0$script`" %*"
        Set-Content -Path $batFile -Value $content
        Write-Success "  Created wrapper: $script.cmd"
    }

    # Add to PATH if not already there
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$InstallDir*") {
        Write-Info "Adding $InstallDir to user PATH..."
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$InstallDir", "User")
        Write-Success "Added to PATH (restart terminal to take effect)"
    } else {
        Write-Success "Already in PATH"
    }

    Write-Host ""
    Write-Warn "Note: set-core scripts require Git Bash or WSL to run."
    Write-Host "  The .cmd wrappers will call bash automatically."
}

function Install-ClaudeCode {
    Write-Info "Checking Claude Code CLI..."

    if (Test-Command "claude") {
        $version = & claude --version 2>&1 | Select-Object -First 1
        Write-Success "Claude Code CLI already installed: $version"
        return
    }

    if (-not (Test-Command "npm")) {
        Write-Warn "npm not found. Skipping Claude Code CLI installation."
        Write-Host "  Install Node.js first, then run: npm install -g @anthropic-ai/claude-code"
        return
    }

    Write-Host "Installing Claude Code CLI..."
    npm install -g @anthropic-ai/claude-code

    if (Test-Command "claude") {
        Write-Success "Claude Code CLI installed"
    } else {
        Write-Warn "Claude Code CLI installation may have failed"
    }
}

function Install-GuiDependencies {
    Write-Info "Installing GUI Python dependencies..."

    $pythonCmd = $null
    if (Test-Command "python") {
        $pythonCmd = "python"
    } elseif (Test-Command "python3") {
        $pythonCmd = "python3"
    } else {
        Write-Warn "Python not found. Skipping GUI dependencies."
        Write-Host "  Install Python first: winget install Python.Python.3.12"
        return
    }

    $requirementsFile = Join-Path $ScriptDir "gui\requirements.txt"

    if (-not (Test-Path $requirementsFile)) {
        Write-Warn "GUI requirements.txt not found"
        return
    }

    Write-Info "Installing from requirements.txt..."
    try {
        & $pythonCmd -m pip install -r $requirementsFile
        Write-Success "GUI dependencies installed (PySide6, psutil, etc.)"
    } catch {
        Write-Warn "Some GUI dependencies may have failed to install"
        Write-Host "  Try manually: pip install -r $requirementsFile"
    }

    # Install optional pywin32 for better window management
    Write-Info "Installing optional pywin32 for window management..."
    try {
        & $pythonCmd -m pip install pywin32
        Write-Success "pywin32 installed"
    } catch {
        Write-Warn "pywin32 installation failed (optional)"
    }
}

function Install-Skills {
    Write-Info "Installing Claude Code skills and commands..."

    $claudeDir = Join-Path $env:USERPROFILE ".claude"

    # Create skills directory
    $skillsDir = Join-Path $claudeDir "skills"
    if (-not (Test-Path $skillsDir)) {
        New-Item -ItemType Directory -Path $skillsDir -Force | Out-Null
    }

    # Create commands directory
    $commandsDir = Join-Path $claudeDir "commands"
    if (-not (Test-Path $commandsDir)) {
        New-Item -ItemType Directory -Path $commandsDir -Force | Out-Null
    }

    # Copy set skills
    $srcSkills = Join-Path $ScriptDir ".claude\skills\set"
    $dstSkills = Join-Path $skillsDir "set"
    if (Test-Path $srcSkills) {
        if (Test-Path $dstSkills) {
            Remove-Item $dstSkills -Recurse -Force
        }
        Copy-Item $srcSkills $dstSkills -Recurse
        Write-Success "  Copied: skills/set/"
    }

    # Copy set commands
    $srcCommands = Join-Path $ScriptDir ".claude\commands\set"
    $dstCommands = Join-Path $commandsDir "set"
    if (Test-Path $srcCommands) {
        if (Test-Path $dstCommands) {
            Remove-Item $dstCommands -Recurse -Force
        }
        Copy-Item $srcCommands $dstCommands -Recurse
        Write-Success "  Copied: commands/set/"
    }

}

function Install-Zed {
    Write-Info "Checking Zed editor..."

    if (Test-Command "zed") {
        Write-Success "Zed editor already installed"
        return
    }

    # Check common install locations
    $zedPaths = @(
        "$env:LOCALAPPDATA\Programs\Zed\zed.exe",
        "$env:ProgramFiles\Zed\zed.exe"
    )

    foreach ($path in $zedPaths) {
        if (Test-Path $path) {
            Write-Success "Zed editor found at: $path"
            return
        }
    }

    Write-Host ""
    $response = Read-Host "Zed editor not found. Open download page? [Y/n]"
    if ($response -match "^[Nn]") {
        Write-Warn "Skipping Zed installation"
        return
    }

    Start-Process "https://zed.dev/download"
    Write-Host "Please download and install Zed from the opened page."
}

# Main
function Main {
    Write-Host ""
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host "  set-core Installer (Windows)" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host ""

    Check-Prerequisites
    Write-Host ""

    Install-Scripts
    Write-Host ""

    Install-ClaudeCode
    Write-Host ""

    Install-GuiDependencies
    Write-Host ""

    Install-Skills
    Write-Host ""

    Install-Zed
    Write-Host ""

    Write-Host "================================" -ForegroundColor Cyan
    Write-Success "Installation complete!"
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Quick start (in Git Bash, PowerShell, or CMD):"
    Write-Host "  cd /path/to/your/project"
    Write-Host "  set-project init"
    Write-Host "  set-new my-change"
    Write-Host "  set-work my-change"
    Write-Host ""
    Write-Host "GUI Control Center (requires Python):"
    Write-Host "  python gui/main.py"
    Write-Host ""
}

Main
