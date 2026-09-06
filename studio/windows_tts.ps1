param([Parameter(Mandatory=$true)][string]$InputJson)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$request = Get-Content -LiteralPath $InputJson -Raw -Encoding UTF8 | ConvertFrom-Json
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voices = @($speaker.GetInstalledVoices() | Where-Object { $_.Enabled })
    $korean = $voices | Where-Object { $_.VoiceInfo.Culture.Name -eq 'ko-KR' } | Select-Object -First 1
    $english = $voices | Where-Object { $_.VoiceInfo.Culture.Name -like 'en-*' } | Select-Object -First 1
    foreach ($item in $request.items) {
        if ($item.text -match '[\uAC00-\uD7A3]' -and $null -ne $korean) {
            $speaker.SelectVoice($korean.VoiceInfo.Name)
        } elseif ($null -ne $english) {
            $speaker.SelectVoice($english.VoiceInfo.Name)
        }
        $speaker.Rate = 0
        $speaker.SetOutputToWaveFile([string]$item.path)
        $speaker.Speak([string]$item.text)
        $speaker.SetOutputToNull()
    }
} finally {
    $speaker.Dispose()
}
