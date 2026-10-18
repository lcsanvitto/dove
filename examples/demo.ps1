# Demo rápido do Dove: claude <-> hermes
$env:A2A_HOME = Join-Path $env:TEMP ("dove-demo-" + [guid]::NewGuid())
$a2a = Join-Path $PSScriptRoot "..\a2a.py"
python $a2a init
python $a2a join --agent claude
python $a2a join --agent hermes
python $a2a send --from claude --to hermes --project demo --kind task --body "revisar o modulo X"
Write-Host "--- caixa do hermes ---"
python $a2a inbox --agent hermes
Write-Host "Caixa (A2A_HOME): $env:A2A_HOME"
