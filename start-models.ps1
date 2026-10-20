# Starts the 3 Python ML services, each in its own window. Run backend and frontend separately.
# One-time setup:
#   py -3.11 -m venv ml-service\.venv
#   ml-service\.venv\Scripts\python -m pip install -r ai-vehicle-health-assessment\requirements.txt fastapi uvicorn
#   py -3.15 -m venv vehical-hidden-fault-and-mitigation\.venv    (xgboost 3.4.1 needs Python 3.12+)
#   vehical-hidden-fault-and-mitigation\.venv\Scripts\python -m pip install -r vehical-hidden-fault-and-mitigation\requirements.txt
#   vehical-hidden-fault-and-mitigation\.venv\Scripts\python -m pip install --no-deps -r vehical-hidden-fault-and-mitigation\requirements-expert.txt
#   py -3.11 -m venv Component3-Deterioration\.venv
#   Component3-Deterioration\.venv\Scripts\python -m pip install -r Component3-Deterioration\requirements.txt

$root = $PSScriptRoot

function Start-Model($title, $dir, $cmd) {
    Start-Process powershell -ArgumentList '-NoExit', '-Command', "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location '$dir'; $cmd"
}

Start-Model 'ML health :8001' $root '.\ml-service\.venv\Scripts\python -m uvicorn server:app --app-dir ml-service --port 8001'
Start-Model 'Hidden fault :8002' "$root\vehical-hidden-fault-and-mitigation" '.\.venv\Scripts\python -m uvicorn api:app --port 8002'
Start-Model 'Deterioration :8003' "$root\Component3-Deterioration" '.\.venv\Scripts\python -m uvicorn app:app --port 8003'

Write-Host 'Models started on ports 8001, 8002, 8003.'
