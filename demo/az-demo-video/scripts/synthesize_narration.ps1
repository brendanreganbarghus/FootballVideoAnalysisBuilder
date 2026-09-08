param(
  [string]$ScenesJson = "$PSScriptRoot\scenes.json",
  [string]$OutDir = "$PSScriptRoot\..\build\audio",
  [string]$VoiceName = "Mark",
  # Optional: re-synthesize only specific scene IDs (e.g. -OnlyIds 5), instead
  # of the whole narration. Useful when a single scene's text is corrected.
  [int[]]$OnlyIds = $null
)

# FALLBACK narration synthesizer. Generates one WAV narration file per scene
# using the WinRT Windows.Media.SpeechSynthesis API (gives access to the
# modern "Microsoft Mark" OneCore voice, which the older System.Speech/SAPI5
# desktop API cannot select on this platform).
#
# This is the offline fallback: it needs no internet access, unlike the
# PRIMARY synthesizer, scripts/synthesize_narration_edge.py, which uses the
# `edge-tts` Python package for a more natural, expressive Microsoft neural
# voice (default en-GB-RyanNeural) but requires internet access to
# Microsoft's Edge TTS endpoint at synthesis time. Use this script only if
# edge-tts / that internet access is unavailable -- the resulting "Mark"
# voice is functional but noticeably more flat/robotic than the neural
# voice, and this script only supports the single pace built into
# scenes.json (no fast/relaxed pace-preset split).
#
# IMPORTANT: this WinRT type-literal projection
# ([Type,Assembly,ContentType=WindowsRuntime]) only resolves under Windows
# PowerShell 5.1 (powershell.exe), not PowerShell 7 (pwsh.exe). Run with:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File synthesize_narration.ps1

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

[Windows.Media.SpeechSynthesis.SpeechSynthesizer,Windows.Media.SpeechSynthesis,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -like "*$VoiceName*" } | Select-Object -First 1
if ($voice) {
  $synth.Voice = $voice
  Write-Host "Using voice: $($voice.DisplayName)"
} else {
  Write-Host "Voice '$VoiceName' not found, using default: $($synth.Voice.DisplayName)"
}

$scenes = Get-Content -Raw -Path $ScenesJson | ConvertFrom-Json

foreach ($scene in $scenes) {
  $id = $scene.id
  if ($OnlyIds -and ($OnlyIds -notcontains $id)) { continue }
  $text = $scene.text
  $outPath = Join-Path $OutDir ("scene{0:D2}.wav" -f $id)

  $stream = Await ($synth.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])

  $dataReader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
  Await ($dataReader.LoadAsync([uint32]$stream.Size)) ([uint32]) | Out-Null
  $buffer = New-Object byte[] $stream.Size
  $dataReader.ReadBytes($buffer)
  [System.IO.File]::WriteAllBytes($outPath, $buffer)

  Write-Host ("Scene {0}: {1} -> {2} ({3} bytes)" -f $id, $scene.title, $outPath, $buffer.Length)
}

Write-Host "All scenes synthesized with WinRT voice."
