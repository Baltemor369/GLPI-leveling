# Ferme les instances Streamlit existantes et relance l'application
Write-Host "Arret des instances Streamlit en cours..." -ForegroundColor Yellow
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*streamlit*"
} | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name streamlit -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1
Write-Host "Lancement de GlpiLeveling..." -ForegroundColor Green
Set-Location $PSScriptRoot
& ".\.venv\Scripts\activate.ps1"
streamlit run app/Aventurier.py --server.port 8501
