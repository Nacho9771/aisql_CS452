param(
    [string]$Question = '',
    [ValidateSet('zero_shot','single_domain','cross_domain')]
    [string]$Strategy = 'zero_shot',
    [switch]$Examples,
    [switch]$CheckDb,
    [switch]$Test
)
$ErrorActionPreference = 'Stop'
$localPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $localPython) { $projectPython = $localPython }
elseif (Test-Path -LiteralPath $bundledPython) { $projectPython = $bundledPython }
else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand -or $pythonCommand.Source -like '*WindowsApps*') {
        throw 'Install Python 3.10+ or create a local .venv before running this project.'
    }
    $projectPython = $pythonCommand.Source
}
Push-Location $PSScriptRoot
try {
    if ($Test) { & $projectPython -m unittest -v test_db_bot test_api_errors }
    elseif ($Examples) { & $projectPython (Join-Path $PSScriptRoot 'run_examples.py') }
    elseif ($CheckDb) { & $projectPython (Join-Path $PSScriptRoot 'db_bot.py') --check-db }
    elseif ($Question) { & $projectPython (Join-Path $PSScriptRoot 'db_bot.py') --strategy $Strategy --question $Question }
    else { & $projectPython (Join-Path $PSScriptRoot 'db_bot.py') --strategy $Strategy }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }
