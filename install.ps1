# Instalador do Dove (Windows). Idempotente - pode rodar de novo sem problema.
# Uso: powershell -ExecutionPolicy Bypass -File install.ps1 [-Agents claude,codex,hermes] [-Instructions]
#   -Instructions: grava o nucleo do Dove nos arquivos globais do Claude Code e do Codex (a2a instructions install)
param([string[]]$Agents = @("claude", "codex", "hermes"), [switch]$Instructions)
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $repo "a2a.py"
if (-not (Test-Path $script)) { Write-Error "a2a.py nao encontrado em $repo"; exit 1 }

# Python: prefere o launcher py; rejeita o atalho da Microsoft Store
function Test-Python($cmd) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { return $false }
    try { $out = (& $cmd --version 2>&1 | Out-String) } catch { return $false }
    if ($LASTEXITCODE -ne 0 -or $out -match "Microsoft Store" -or $out -notmatch "Python 3") { return $false }
    return $true
}
$py = $null
foreach ($c in @("py", "python")) { if (Test-Python $c) { $py = $c; break } }
if (-not $py) {
    Write-Host "ERRO: Python 3 nao encontrado (nem 'py' nem 'python')." -ForegroundColor Red
    Write-Host "Instale com: winget install Python.Python.3.13   e abra um PowerShell novo."
    exit 1
}
Write-Host "Python: $py ($((& $py --version 2>&1 | Out-String).Trim()))"

# $HOME\bin\a2a.cmd chama o a2a.py do repo (git pull atualiza a ferramenta)
$bin = Join-Path $HOME "bin"
if (-not (Test-Path $bin)) { New-Item -ItemType Directory -Path $bin | Out-Null }
$cmdFile = Join-Path $bin "a2a.cmd"
Set-Content -Path $cmdFile -Value "@$py `"$script`" %*" -Encoding Ascii
Write-Host "atalho: $cmdFile"

# $HOME\bin\a2a (sem extensao): shim POSIX para o Git Bash (Claude Code e Hermes no Windows),
# que nao resolve a2a -> a2a.cmd. LF, sem BOM.
$shFile = Join-Path $bin "a2a"
$posixScript = $script -replace "\\", "/"
$shContent = "#!/bin/sh`nexec $py `"$posixScript`" `"`$@`"`n"
[System.IO.File]::WriteAllText($shFile, $shContent, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "atalho: $shFile (Git Bash)"

# dove = a2a panel --open (app no navegador): dove.cmd + shim Git Bash
$doveCmd = Join-Path $bin "dove.cmd"
Set-Content -Path $doveCmd -Value "@$py `"$script`" panel --open %*" -Encoding Ascii
Write-Host "atalho: $doveCmd"
$doveSh = Join-Path $bin "dove"
$doveContent = "#!/bin/sh`nexec $py `"$posixScript`" panel --open `"`$@`"`n"
[System.IO.File]::WriteAllText($doveSh, $doveContent, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "atalho: $doveSh (Git Bash)"

# PATH do usuario (sem duplicar) e da sessao atual
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @(); if ($userPath) { $parts = @($userPath -split ";" | Where-Object { $_ }) }
if (-not ($parts | Where-Object { $_.TrimEnd("\") -ieq $bin.TrimEnd("\") })) {
    [Environment]::SetEnvironmentVariable("Path", ((@($parts) + $bin) -join ";"), "User")
    Write-Host "PATH do usuario: adicionado $bin"
} else { Write-Host "PATH do usuario: $bin ja estava" }
if (-not (($env:Path -split ";") | Where-Object { $_.TrimEnd("\") -ieq $bin.TrimEnd("\") })) {
    $env:Path = "$env:Path;$bin"
}

# Canal e agentes
& $py $script init
foreach ($ag in $Agents) { & $py $script join --agent $ag }

# Instrucoes globais (todos os projetos): so com -Instructions
if ($Instructions) { & $py $script instructions install --agents "claude,codex" }

Write-Host ""
Write-Host "Dove instalado." -ForegroundColor Green
Write-Host "  repo:    $repo"
Write-Host "  atalho:  $cmdFile (PowerShell/cmd)"
Write-Host "  atalho:  $shFile (Git Bash - Claude Code e Hermes no Windows)"
Write-Host "  app:     $doveCmd (dove: abre o painel no navegador)"
Write-Host "  agentes: $($Agents -join ', ')"
Write-Host "  atualizar: git -C `"$repo`" pull"
Write-Host ""
if (-not $Instructions) { Write-Host "Para valer em todos os projetos: a2a instructions install" }
Write-Host "Feche e abra um PowerShell novo e rode: a2a status   (ou: dove, para abrir o app)"
Write-Host 'Se um agente no Git Bash nao achar o a2a, rode no Git Bash: echo ''export PATH="$HOME/bin:$PATH"'' >> ~/.bashrc'
