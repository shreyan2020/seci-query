# SECI Persona Studio

SECI Persona Studio is a desktop research workspace for exploring underspecified biotech questions with persona-guided reasoning, literature evidence, project memory, and draft/report workflows.

The current Windows installer is:

`frontend/dist/SECI-Persona-Studio-0.1.0-x64.exe`

## What Stakeholders Can Do

- Create and open research projects.
- Add project goals, target hosts, and desired end products.
- Explore a question through collaborator personas and objective modes.
- Review literature-backed findings and evidence trails.
- Capture judgment calls, gaps, proposal seeds, and working drafts.
- Open project journey summaries that show how a project evolved.
- Generate and review report drafts from the workspace.

## Install the Windows App

### Prerequisites

Install these before launching the app:

1. Python 3.11 or newer, available on PATH.
2. The backend Python dependencies.
3. Ollama from https://ollama.com.
4. The Ollama model used by the app.

Install backend dependencies from the project folder:

```powershell
cd backend
pip install -r requirements.txt
```

Recommended model setup:

```powershell
ollama pull qwen2.5:7b
ollama serve
```

If `ollama serve` says Ollama is already running, that is fine.

### Install

1. Open `frontend/dist`.
2. Run `SECI-Persona-Studio-0.1.0-x64.exe`.
3. Choose an install location when prompted.
4. Launch **SECI Persona Studio** from the installer, Start Menu, or desktop shortcut.

Windows may show a security warning because the installer is locally built and not code-signed with an organization certificate. Choose **More info** and **Run anyway** only if you trust the source of this build.

## First Launch

On startup, the desktop app launches:

- the bundled Next.js user interface,
- the bundled FastAPI backend,
- a local runtime data folder under the user's app data directory.

Ollama is not bundled. Keep Ollama running locally while using AI-powered features.

The app creates this editable config file on first launch:

`%APPDATA%\SECI Persona Studio\app-config.json`

Default config:

```json
{
  "ollamaBaseUrl": "http://localhost:11434",
  "ollamaModel": "qwen2.5:7b"
}
```

To use another local Ollama model, pull it first, edit `ollamaModel`, and restart the app.

## Basic Usage

1. Launch **SECI Persona Studio**.
2. Create or select a project.
3. Define the project goal, target host, and desired end product.
4. Add a research question.
5. Select a collaborator persona and objective mode.
6. Review generated objectives, evidence, gaps, judgments, and proposal seeds.
7. Use the journey view to revisit prior exploration paths.
8. Use report and draft tools to turn workspace findings into shareable outputs.

## Troubleshooting

### App Opens With a Startup Error

Check that Python is installed and available:

```powershell
python --version
```

Then install backend dependencies if needed:

```powershell
cd backend
pip install -r requirements.txt
```

### AI Responses Fail

Check that Ollama is running:

```powershell
ollama serve
```

Check that the configured model exists:

```powershell
ollama list
```

If needed:

```powershell
ollama pull qwen2.5:7b
```

### Port Conflicts

The backend uses `127.0.0.1:8000`. Close other local services using that port before launching the desktop app.

## Server Deployment With Docker Compose

The compose setup runs four services:

- `nginx` on port `80`, the public entrypoint
- `frontend` on Docker's internal network
- `backend` on Docker's internal network
- `worker` for report rendering jobs
- `ollama` on Docker's internal network only, so it will not conflict with a host Ollama on port `11434`

Create a deployment environment file from the example:

```bash
cp .env.example .env
```

For a simple server where users open `http://SERVER_HOST`, set:

```env
NGINX_BIND=0.0.0.0
NGINX_PORT=80
NEXT_PUBLIC_API_URL=/
NEXT_PUBLIC_API_PORT=
CORS_ORIGINS=http://SERVER_HOST
```

Using `NEXT_PUBLIC_API_URL=/` makes browser API calls stay on the same origin through nginx. If the API is behind a different domain, set `NEXT_PUBLIC_API_URL` to the full public API origin instead.

Build and start:

```bash
docker compose up --build -d
```

Check the services:

```bash
docker compose ps
docker compose logs -f backend frontend worker ollama
```

Pull the model inside the Ollama container before using AI-powered flows:

```bash
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

Open the app at `http://SERVER_HOST`. The proxied backend health check is available at `http://SERVER_HOST/health`.

## Developer Setup

### Run in Development Mode

Install dependencies:

```powershell
cd frontend
npm install
```

Install backend dependencies:

```powershell
cd ..\backend
pip install -r requirements.txt
```

Start the desktop development environment:

```powershell
cd ..\frontend
npm run desktop:dev
```

This starts:

- FastAPI on `127.0.0.1:8000`
- Next.js on `http://localhost:3000`
- Electron as a desktop shell

### Build the Windows Installer

From `frontend`:

```powershell
npm run desktop:dist:win
```

If the global `npm` shim is broken, run the project-local commands directly:

```powershell
$env:NEXT_TELEMETRY_DISABLED='1'
.\node_modules\.bin\next.cmd build
.\node_modules\.bin\electron-builder.cmd --win nsis
```

The installer is written to `frontend/dist`.

## Project Structure

```text
frontend/              Next.js and Electron desktop app
frontend/electron/     Electron main and preload scripts
backend/               FastAPI backend and research services
backend/data/          Local seed/demo data
docker-compose.yml     Optional container setup
```

## Notes for Sharing

- Share the installer `.exe` from `frontend/dist`.
- Share `frontend/dist/README-for-stakeholders.md` alongside the installer.
- Tell stakeholders to install Python and Ollama first.
- Tell stakeholders which Ollama model to pull.
- Ask stakeholders to click **Export Diagnostics** from an open project if they see a failure, weak literature results, poor annotations, or a confusing generated draft.
- Do not share local runtime data from `%APPDATA%` unless intentionally exporting a user-specific project state.
