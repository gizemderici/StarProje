$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceFile = Join-Path $ProjectDir 'star-energy-api-studio.code-workspace'
$CodeCommand = Get-Command code -ErrorAction SilentlyContinue
if (-not $CodeCommand) {
    throw 'VS Code komutu bulunamadı. VS Code içinde "Shell Command: Install code command" seçeneğini çalıştırın.'
}
Start-Process -FilePath $CodeCommand.Source -ArgumentList @($WorkspaceFile)
