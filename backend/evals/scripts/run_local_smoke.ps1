Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BackendDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $BackendDir
try {
    python -m evals.run_suite --config evals/suites/local_smoke.json --output-dir data/eval_runs/local_smoke
}
finally {
    Pop-Location
}
