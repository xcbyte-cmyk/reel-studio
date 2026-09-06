$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force -Path "$PSScriptRoot\data" | Out-Null
$reelUrl = 'http://127.0.0.1:18765'
try {
    $reelHealth = Invoke-RestMethod -Uri "$reelUrl/api/health" -TimeoutSec 2
    if ($reelHealth.name -eq 'Reel Studio') {
        Start-Process $reelUrl
        exit 0
    }
} catch {}
$reelPython = (Get-Command python -ErrorAction Stop).Source
& $reelPython -c 'import PIL, requests'
if ($LASTEXITCODE -ne 0) {
    & $reelPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw 'FFmpeg is required. Install with: winget install --id Gyan.FFmpeg -e'
}
$reelArgs = @('server.py', '--port', '18765')
Start-Process -FilePath $reelPython -ArgumentList $reelArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\data\server.log" -RedirectStandardError "$PSScriptRoot\data\server-error.log"
for ($reelAttempt = 0; $reelAttempt -lt 30; $reelAttempt++) {
    Start-Sleep -Milliseconds 300
    try {
        $reelHealth = Invoke-RestMethod -Uri "$reelUrl/api/health" -TimeoutSec 2
        if ($reelHealth.name -eq 'Reel Studio') { Start-Process $reelUrl; exit 0 }
    } catch {}
}
throw 'Startup failed. See data/server-error.log.'
