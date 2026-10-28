# Baixa (uma vez, com internet) os binários Windows usados pelas skills para a pasta tools\
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tools = Join-Path $root "tools"
New-Item -ItemType Directory -Force -Path $tools | Out-Null
$headers = @{ "User-Agent" = "CodeReviewLocal" }
if ($env:GITHUB_TOKEN) { $headers["Authorization"] = "Bearer $env:GITHUB_TOKEN" }  # evita limite da API no CI

function Get-Asset($repo, $pattern) {
    $rel = Invoke-RestMethod -Headers $headers "https://api.github.com/repos/$repo/releases/latest"
    $asset = $rel.assets | Where-Object { $_.name -match $pattern } | Select-Object -First 1
    if (-not $asset) { throw "Nenhum arquivo '$pattern' na release $($rel.tag_name) de $repo" }
    Write-Host "  $repo $($rel.tag_name): $($asset.name)"
    $dest = Join-Path $env:TEMP $asset.name
    Invoke-WebRequest -Headers $headers $asset.browser_download_url -OutFile $dest
    return $dest
}

Write-Host "Gitleaks..."
$z = Get-Asset "gitleaks/gitleaks" "windows_x64\.zip$"
Expand-Archive $z -DestinationPath (Join-Path $tools "gitleaks") -Force
Copy-Item (Join-Path $tools "gitleaks\gitleaks.exe") $tools -Force

Write-Host "OSV-Scanner..."
$f = Get-Asset "google/osv-scanner" "windows_amd64\.exe$"
Copy-Item $f (Join-Path $tools "osv-scanner.exe") -Force

Write-Host "Ruff..."
$z = Get-Asset "astral-sh/ruff" "x86_64-pc-windows-msvc\.zip$"
Expand-Archive $z -DestinationPath (Join-Path $tools "ruff") -Force
Copy-Item (Get-ChildItem (Join-Path $tools "ruff") -Recurse -Filter ruff.exe | Select-Object -First 1).FullName $tools -Force

Write-Host "DevSkim..."
try {
    $z = Get-Asset "microsoft/DevSkim" "win-x64.*\.zip$"
    Expand-Archive $z -DestinationPath (Join-Path $tools "devskim") -Force
    $exe = Get-ChildItem (Join-Path $tools "devskim") -Recurse -Filter devskim.exe | Select-Object -First 1
    if ($exe) { Write-Host "  devskim.exe em $($exe.FullName)" }
} catch {
    Write-Warning "DevSkim sem binário Windows na release; tentando como dotnet tool..."
    dotnet tool install Microsoft.CST.DevSkim.CLI --tool-path (Join-Path $tools "devskim")
}

Write-Host "Pronto. Ferramentas em $tools"
