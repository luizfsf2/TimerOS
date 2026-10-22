# Desenvolvimento local da I02 (Windows PowerShell). Nao e o executor de QA.
# Executa somente na branch autorizada, sem Git push/merge/CI/PR.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

function RunChecked([string]$Label, [string]$Program, [string[]]$Arguments) {
    Write-Host ""
    Write-Host "==> $Label"
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label falhou: exit $LASTEXITCODE"
    }
}

$branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne "feature/v1") {
    throw "Execute somente na branch feature/v1."
}
$dirty = & git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "git status falhou." }
if ($dirty) { throw "Working tree nao esta limpo. Preserve e reconcilie alteracoes antes de rodar." }

RunChecked "Rust" "rustc" @("--version")
RunChecked "Cargo" "cargo" @("--version")
RunChecked "Resolver dependencias reais da I02" "cargo" @("generate-lockfile")
RunChecked "Aplicar formatacao mecanica" "cargo" @("fmt", "--all")
RunChecked "Verificar lock deterministico" "cargo" @("fetch", "--locked")
RunChecked "Verificar formato" "cargo" @("fmt", "--all", "--", "--check")
RunChecked "Suite completa" "cargo" @("test", "--locked", "--all-targets")
RunChecked "Suite com desktop" "cargo" @("test", "--locked", "--all-targets", "--features", "desktop")
RunChecked "Clippy completo" "cargo" @("clippy", "--locked", "--all-targets", "--", "-D", "warnings")
RunChecked "Clippy desktop" "cargo" @("clippy", "--locked", "--all-targets", "--features", "desktop", "--", "-D", "warnings")
RunChecked "Build Windows" "cargo" @("build", "--locked", "--features", "desktop", "--bin", "timeros")

Write-Host ""
Write-Host "Verificacoes automatizadas concluiram sem erro."
Write-Host "Inspecione o diff de Cargo.lock e os arquivos formatados antes de commitar."
& git status --short
& git diff --stat
Write-Host "Teste manual GUI permanece obrigatorio: cargo run --locked --features desktop --bin timeros"
Write-Host "Nao executar PACOTE_QA ate concluir correcoes, commit e publicacao."
