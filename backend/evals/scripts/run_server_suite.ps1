param(
    [string]$Config = "evals/suites/server_biomed_template.json",
    [string]$OutputDir = "data/eval_runs/server_biomed",
    [switch]$IncludeDisabled,
    [switch]$FailFast
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BackendDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $BackendDir
try {
    $ArgsList = @("-m", "evals.run_suite", "--config", $Config, "--output-dir", $OutputDir)
    if ($IncludeDisabled) {
        $ArgsList += "--include-disabled"
    }
    if ($FailFast) {
        $ArgsList += "--fail-fast"
    }
    python @ArgsList
}
finally {
    Pop-Location
}
