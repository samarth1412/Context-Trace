param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WorkDir = Join-Path $RootDir ".tmp-release-assets"
$StagingDir = Join-Path $WorkDir "contexttrace-benchmark-evidence-v$Version"
$ArchivePath = Join-Path $WorkDir "contexttrace-benchmark-evidence-v$Version.zip"
$EvidencePaths = @(
    "benchmarks/contexttrace_bench/out/ragtruth_release_bundle",
    "benchmarks/contexttrace_bench/out/ares_nq_example/smoke200_compared_bundle",
    "benchmarks/contexttrace_bench/out/crag_official/review200_ragchecker_bundle",
    "benchmarks/contexttrace_bench/out/diag150_release_bundle",
    "benchmarks/contexttrace_bench/out/ragtruth_independent_signoff"
)

function Remove-SafePath {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $Resolved = (Resolve-Path -LiteralPath $Path).Path
    if (-not $Resolved.StartsWith($WorkDir, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove outside release work directory: $Resolved"
    }
    Remove-Item -LiteralPath $Resolved -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
Remove-SafePath $StagingDir
Remove-SafePath $ArchivePath
New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null

foreach ($RelativePath in $EvidencePaths) {
    $Source = Join-Path $RootDir $RelativePath
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Missing evidence directory: $RelativePath"
    }
    $Destination = Join-Path $StagingDir $RelativePath
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse
}

$Files = Get-ChildItem -LiteralPath $StagingDir -Recurse -File | Sort-Object FullName
$Artifacts = foreach ($File in $Files) {
    $Relative = $File.FullName.Substring($StagingDir.Length + 1).Replace("\", "/")
    [ordered]@{
        path = $Relative
        bytes = $File.Length
        sha256 = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$Commit = (& git -C $RootDir rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Unable to resolve the source commit"
}

$Manifest = [ordered]@{
    schema_version = 1
    release = "v$Version"
    source_commit = $Commit
    generated_at = [DateTimeOffset]::UtcNow.ToString("o")
    claim_policy = "Calibration evidence; broad SOTA claims remain blocked until every independent-review gate passes."
    artifacts = @($Artifacts)
}
$ManifestPath = Join-Path $StagingDir "evidence-manifest.json"
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ManifestPath -Encoding utf8

Compress-Archive -Path (Join-Path $StagingDir "*") -DestinationPath $ArchivePath -CompressionLevel Optimal
$ArchiveHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()

Write-Host "Created $ArchivePath"
Write-Host "SHA256 $ArchiveHash"
