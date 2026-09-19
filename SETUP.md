# DreamCoder setup

## 1. Install
pip install -r requirements-dev.txt
cd electron && npm install && cd ..

## 2. Configure
Copy .env.example to .env. Configure only Ollama endpoints you own or have explicit permission to use.

## 3. Start backend
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

## 4. Open the IDE
Use the Electron application, or serve frontend/ with python -m http.server 3000.

For the GitHub Pages-hosted UI shell, deploy the static frontend from the `frontend/` folder and keep the backend running locally or behind a reachable remote API URL.

## 5. Configure Ollama
Open Models, enter an Ollama host, select Load, then choose a ranked model to make it primary.

## 6. Verify
- GET /api/quota shows HF quota and local lane status.
- GET /api/ollama/primary shows the configured primary.
- Toolbar Sync mirrors indexed files to GitHub.

## Agent shell
Restricted execution is the default. Set DREAMCODER_AGENT_UNRESTRICTED=1 only for trusted local development. Commands are logged to the audit file.

## Backups
When GitHub sync fails, generated file contents are preserved as ZIP backups under DREAMCODER_BACKUP_DIR.
