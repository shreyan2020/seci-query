# Desktop App (Windows)

This project now supports a native desktop shell using Electron.

## Prerequisites
- Node.js installed
- Python installed and available in PATH
- Backend dependencies installed: `pip install -r ../backend/requirements.txt`
- Ollama installed and running
- Required Ollama model pulled (as configured by backend env)

## Run desktop in dev mode
From `frontend`:

```powershell
npm install
npm run desktop:dev
```

This starts:
- FastAPI on `127.0.0.1:8000`
- Next.js on `localhost:3000`
- Electron app window

## Build Windows installer (.exe)
From `frontend`:

```powershell
npm install
npm run desktop:dist:win
```

Output will be under `frontend/dist` (NSIS setup `.exe`).

## Runtime behavior of packaged app
- Frontend server is bundled and started by Electron.
- Backend code is bundled and started by Electron.
- Ollama is NOT bundled; user must install/run it separately.
- Backend writable runtime data goes to the app user data directory.

## Ollama model config
The packaged app creates a user-editable config file on first launch:

`%APPDATA%\SECI Persona Studio\app-config.json`

Example:

```json
{
  "ollamaBaseUrl": "http://localhost:11434",
  "ollamaModel": "qwen2.5:7b"
}
```

You can change `ollamaModel` to any model you have pulled locally, for example:

```powershell
ollama pull llama3.1:8b
```

Then update `app-config.json` and restart the app.
