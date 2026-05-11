# Serviq - Local AI Agent

Production-grade local AI agent powered by LM Studio, FastAPI, Tauri, SQLite, and Qdrant.

## Project Structure

```
.
├── apps/desktop/          # Tauri desktop app (React + Vite + TypeScript)
│   ├── src/              # React frontend source
│   │   ├── components/   # UI components (shell, panels)
│   │   ├── hooks/        # Custom React hooks (health, LM Studio)
│   │   └── lib/          # API utilities (api.ts, config.ts, llmApi.ts)
│   ├── src-tauri/        # Rust Tauri backend
│   └── package.json      # Desktop app dependencies
│
├── backend/               # FastAPI Python backend
│   ├── api/routes/       # API endpoints (health, llm)
│   ├── core/             # Config, logging, middleware, errors
│   ├── db/               # Database initialization & session
│   ├── schemas/          # Pydantic models
│   ├── llm/              # LM Studio client
│   ├── agent/            # Agent implementation (empty)
│   ├── sandbox/          # Code execution sandbox
│   ├── scheduler/        # Task scheduling
│   ├── memory/           # Memory/embedding services
│   ├── tools/            # Agent tools
│   └── main.py           # FastAPI app entry point
│
├── docker/                # Docker configurations
│   ├── qdrant/           # Qdrant volume storage
│   └── sandbox/          # Sandbox container configs
│
├── workspace/             # Runtime workspace (gitignored)
│   ├── notes/            # User notes
│   ├── projects/         # Project files
│   ├── uploads/          # File uploads
│   ├── generated/        # Generated outputs
│   ├── logs/             # Application logs
│   └── serviq.sqlite3   # SQLite database
│
├── scripts/              # Development & utility scripts
├── docker-compose.yml    # Qdrant container definition
└── .env                 # Environment configuration
```

## Tech Stack

- **Desktop**: Tauri 2.x + React 19 + Vite + TypeScript + Tailwind CSS
- **Backend**: FastAPI + Pydantic + aiosqlite + Qdrant client
- **AI**: LM Studio (local LLM via OpenAI-compatible API)
- **Database**: SQLite (via aiosqlite) + Qdrant (vector store)
- **Package Manager**: pnpm (monorepo workspace)

## Available Commands

```bash
# Desktop app
pnpm desktop:dev       # Run Tauri dev server
pnpm desktop:build     # Build Tauri app
pnpm frontend:dev      # Run frontend only

# Backend
pnpm backend:dev      # Start FastAPI backend
pnpm backend:install  # Install backend deps
pnpm backend:check    # Check backend health

# Docker
pnpm qdrant:up        # Start Qdrant container
pnpm qdrant:down      # Stop Qdrant container

# Utilities
pnpm doctor           # Run diagnostics
```

## Backend API

The backend runs on `http://127.0.0.1:8787` by default.

- `GET /` - Root endpoint (service info)
- `GET /api/health` - Basic health check
- `GET /api/health/deep` - Deep health with DB check
- `GET /api/llm/health` - LM Studio connection status
- `GET /api/llm/models` - List available LM Studio models
- `POST /api/llm/chat` - Chat completion
- `POST /api/llm/chat/stream` - Streaming chat
- `POST /api/llm/embeddings` - Generate embeddings

## Configuration

Key environment variables (see `.env`):

- `SERVIQ_ENVIRONMENT` - Environment (development/production)
- `SERVIQ_API_HOST/PORT` - Backend host/port (default: 127.0.0.1:8787)
- `DATABASE_URL` - SQLite connection string
- `QDRANT_URL` - Qdrant vector DB URL (default: http://127.0.0.1:6333)
- `LMSTUDIO_BASE_URL` - LM Studio API URL (default: http://127.0.0.1:1234/v1)
- `LMSTUDIO_API_KEY` - LM Studio API key
- `MEMORY_EMBEDDING_MODEL` - Model for embeddings

## LM Studio Integration

The backend communicates with LM Studio via its OpenAI-compatible API. Ensure LM Studio is running locally with:
- HTTP server enabled on port 1234
- A model loaded and ready

## Development Setup

1. Start Qdrant: `pnpm qdrant:up`
2. Start LM Studio and load a model
3. Start backend: `pnpm backend:dev`
4. Start desktop: `pnpm desktop:dev`

## Frontend Components

- `LeftSidebar` - Navigation sidebar
- `ChatWorkspace` - Main chat interface
- `ToolsPanel` - Agent tools panel
- `MemoryPanel` - Memory/recall panel
- `ProductHome` - Home screen
- `SettingsPanel` - Settings UI

## Dependencies

### Desktop (apps/desktop/package.json)
- @tanstack/react-query - Data fetching
- @tauri-apps/api - Tauri APIs
- lucide-react - Icons
- react, react-dom - UI framework
- zustand - State management

### Backend (inferred from code)
- fastapi - Web framework
- pydantic - Data validation
- aiosqlite - Async SQLite
- qdrant-client - Vector DB client
- uvicorn - ASGI server

## Notes

- Backend uses async/await throughout (aiosqlite, async FastAPI)
- SQLite database at `workspace/serviq.sqlite3`
- Qdrant collection named `serviq_memory`
- CORS configured for localhost:1420 (Vite dev server)