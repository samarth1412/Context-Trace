param(
  [string]$Model = "gpt-4.1-mini",
  [int]$Limit = 0,
  [string]$Python = "python",
  [int]$MaxWorkers = 4,
  [int]$ProgressEvery = 25,
  [switch]$Resume,
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir "..\.."))
$OutputDir = Join-Path $ScriptDir "out"
$CandidateInputs = Join-Path $OutputDir "candidate_inputs.jsonl"
$RagasPredictions = Join-Path $OutputDir "ragas_predictions.json"
$DeepEvalPredictions = Join-Path $OutputDir "deepeval_predictions.json"
$RagasVenv = Join-Path $env:TEMP "contexttrace-ragas"
$DeepEvalVenv = Join-Path $env:TEMP "contexttrace-deepeval"

function Import-OpenAIKey {
  if (-not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    return
  }

  foreach ($Target in @("User", "Machine")) {
    $Value = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", $Target)
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
      $env:OPENAI_API_KEY = $Value
      return
    }
  }

  $EnvPath = Join-Path $RepoRoot ".env"
  if (Test-Path -LiteralPath $EnvPath) {
    foreach ($Line in Get-Content -LiteralPath $EnvPath) {
      if ($Line -match '^\s*OPENAI_API_KEY\s*=\s*(.+?)\s*$') {
        $Value = $Matches[1].Trim()
        if (($Value.StartsWith('"') -and $Value.EndsWith('"')) -or ($Value.StartsWith("'") -and $Value.EndsWith("'"))) {
          $Value = $Value.Substring(1, $Value.Length - 2)
        }
        if (-not [string]::IsNullOrWhiteSpace($Value)) {
          $env:OPENAI_API_KEY = $Value
          return
        }
      }
    }
  }
}

function Ensure-Venv {
  param(
    [string]$VenvPath,
    [string]$RequirementsPath
  )

  $VenvPython = Join-Path $VenvPath "Scripts\python.exe"
  if (-not (Test-Path -LiteralPath $VenvPython)) {
    py -3.11 -m venv $VenvPath
  }

  if (-not $SkipInstall) {
    & $VenvPython -m pip install --upgrade pip | Out-Host
    if ($LASTEXITCODE -ne 0) {
      throw "pip upgrade failed for $VenvPath."
    }
    & $VenvPython -m pip install -r $RequirementsPath | Out-Host
    if ($LASTEXITCODE -ne 0) {
      throw "pip install failed for $RequirementsPath."
    }
    & $VenvPython -m pip check | Out-Host
    if ($LASTEXITCODE -ne 0) {
      throw "pip check failed for $VenvPath."
    }
  }

  return $VenvPython
}

Import-OpenAIKey
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
  throw "OPENAI_API_KEY is not set. Set it in this shell, your Windows user environment, or .env before running remote evaluator baselines."
}

Push-Location $RepoRoot
try {
  & $Python benchmarks/contexttrace_bench/run_contexttrace.py --mode semantic --case-set all --enforce-sota-gates

  $RagasPython = Ensure-Venv `
    -VenvPath $RagasVenv `
    -RequirementsPath (Join-Path $ScriptDir "requirements-ragas.txt")
  $DeepEvalPython = Ensure-Venv `
    -VenvPath $DeepEvalVenv `
    -RequirementsPath (Join-Path $ScriptDir "requirements-deepeval.txt")

  $LimitArgs = @()
  if ($Limit -gt 0) {
    $LimitArgs = @("--limit", $Limit)
  }
  $ResumeArgs = @()
  if ($Resume) {
    $ResumeArgs = @("--resume")
  }

  & $RagasPython benchmarks/contexttrace_bench/run_ragas.py `
    --input $CandidateInputs `
    --candidate-output $RagasPredictions `
    --model $Model `
    --max-workers $MaxWorkers `
    --progress-every $ProgressEvery `
    @ResumeArgs `
    @LimitArgs

  & $DeepEvalPython benchmarks/contexttrace_bench/run_deepeval.py `
    --input $CandidateInputs `
    --candidate-output $DeepEvalPredictions `
    --model $Model `
    --max-workers $MaxWorkers `
    --progress-every $ProgressEvery `
    @ResumeArgs `
    @LimitArgs

  if ($Limit -gt 0) {
    Write-Host "Wrote limited baseline smoke outputs:"
    Write-Host "  $RagasPredictions"
    Write-Host "  $DeepEvalPredictions"
    Write-Host "Re-run without -Limit to score a full leaderboard row."
  } else {
    & $Python benchmarks/contexttrace_bench/run_contexttrace.py `
      --mode semantic `
      --case-set all `
      --candidate $RagasPredictions `
      --candidate $DeepEvalPredictions
  }
} finally {
  Pop-Location
}
