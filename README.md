# SECI Query Explorer

A proof-of-concept system for exploring underspecified queries using the SECI framework (Socialization, Externalization, Combination, Internalization).

## Features

- **Objective Generation**: Generate multiple interpretations of what "best" could mean in underspecified queries
- **Facet Questions**: Ask clarifying questions that go beyond simple A/B choices
- **Context Augmentation**: Incorporate external evidence from user-provided context
- **Final Answer Synthesis**: Generate comprehensive answers based on selected objectives and user preferences
- **Learning System**: Store and reuse prior knowledge for similar queries
- **QMD Reports**: Create/edit Quarto Markdown reports, enqueue async HTML/PDF renders, and preview/download outputs
- **Persona Extraction**: Build structured personas from interview transcripts via Ollama
- **Persona-aware Orchestration**: Inject persona summary into objective/augment/finalize prompt assembly

## Architecture

- **Frontend**: Next.js with React and Tailwind CSS
- **Backend**: FastAPI with Python
- **Render Worker**: Python polling worker executing `quarto render` asynchronously
- **AI Runtime**: Ollama with qwen2.5:7b-instruct model
- **Storage**: SQLite for logging, reports, jobs, personas, interviews + artifact files under `/data`

## Quick Start

### Prerequisites

1. Install and start Ollama:
```bash
# Install Ollama (follow instructions at https://ollama.ai)
ollama pull qwen2.5:7b-instruct
ollama serve
```

2. Install Python dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Install Node.js dependencies:
```bash
cd frontend
npm install
```

### Running the System

1. Start the backend:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

2. Start the frontend (in a separate terminal):
```bash
cd frontend
npm run dev
```

3. Open http://localhost:3000 in your browser

## Usage Examples

### Example 1: Best Breakfast Options
Query: "best breakfast options"

The system will generate objectives like:
- Health/Nutrition-optimized
- Taste/Indulgence-focused  
- Convenience/Speed-oriented
- Location-based recommendations
- Cultural/Global breakfasts
- Subjective/Preference-based

### Example 2: Enzyme Selection
Query: "find the best enzyme for CHS reaction"

The system will generate objectives like:
- Catalytic efficiency
- Expression feasibility
- Pathway integration
- Stability/robustness
- Engineering potential

## API Endpoints

- `POST /objectives` - Generate objective clusters
- `POST /augment` - Augment with external context
- `POST /finalize` - Generate final answer
- `POST /log_event` - Log events for learning
- `GET /health` - Health check

### QMD reports

- `POST /api/reports` - Create report
- `GET /api/reports` - List reports
- `GET /api/reports/{id}` - Report metadata/status
- `GET /api/reports/{id}/qmd` - Read QMD
- `PUT /api/reports/{id}/qmd` - Update QMD
- `POST /api/reports/{id}/render` - Enqueue render job
- `GET /api/reports/{id}/output/html` - Serve rendered HTML
- `GET /api/reports/{id}/output/pdf` - Serve rendered PDF
- `GET /api/reports/{id}/logs` - Render log tail

### Personas/interviews

- `POST /api/interviews` - Create interview transcript record
- `POST /api/personas/from-interviews` - Create/update persona from interview transcripts
- `GET /api/personas` - List personas (optional `scope_id`)
- `GET /api/personas/{id}` - Get persona detail

## Development

### Project Structure
```
├── frontend/          # Next.js app
├── backend/           # FastAPI app
├── docker-compose.yml # Optional container setup
└── README.md
```

### Adding New Features

1. **Backend**: Add new endpoints in `main.py`
2. **Frontend**: Update React components in `src/app/page.tsx`
3. **Prompts**: Modify prompt templates in `ollama_client.py`
4. **Database**: Update schema in `database.py`

## Docker Setup (Optional)

```bash
docker-compose up
```

This starts `frontend`, `backend`, `worker`, and `ollama`. The backend and worker share `/data` volume for DB + artifacts.

## Acceptance Criteria

✅ Given "best breakfast options":
- Shows 4-6 different objectives (health, indulgence, convenience, etc.)
- Each objective has non-trivial facet questions
- Final answer is coherent with selected objective

✅ Given "find the best enzyme for CHS reaction":
- Objectives reflect scientific optimization criteria
- Facet questions are domain-relevant

✅ Context augmentation:
- Extracts relevant evidence from user context
- Updates answer to incorporate evidence

✅ Event logging and prior storage for learning

## License

MIT License