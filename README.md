# Serviq

<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

**Serviq** is a local-first AI assistant that runs large language models on your own machine through [LM Studio](https://lmstudio.ai/). It combines a FastAPI backend with a cross-platform Tauri desktop app, prioritizing privacy, control, and full data ownership.

> All your data, models, and conversation history stay on your hardware. No cloud dependencies, no external API calls, no data leaving your machine.

## Table of Contents

- [Why Serviq?](#why-serviq)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Running the Application](#running-the-application)
- [Development Scripts](#development-scripts)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Why Serviq?

| Traditional AI Assistants | Serviq |
|--------------------------|--------|
| Data sent to cloud servers | Everything runs locally |
| Subscription/API costs | Free (bring your own model) |
| Limited customization | Fully extensible architecture |
| Internet dependency required | Works offline |
| Privacy concerns | Complete data ownership |

## Features

- **Local-First Architecture** — All data processed on your machine. No cloud dependencies.
- **Bring Your Own Model** — Works with any GGUF/GGML model supported by LM Studio (Llama, Qwen, Mistral, Phi, etc.)
- **Cross-Platform Desktop** — Native desktop app built with Tauri + React
- **FastAPI Backend** — Robust REST API for agent orchestration, memory, and tool management
- **Conversational Agent** — LangGraph-powered agent with reasoning, tool execution, and context awareness
- **Semantic Memory** — Qdrant vector database for similarity search + SQLite for structured storage
- **Tool System** — Extensible tool framework for file operations, web search, calculations, and shell commands
- **Approval Workflow** — Safety-first approach requiring approval for high-risk operations

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Desktop UI** | Tauri 2.x, React 19, Vite, TypeScript, Tailwind CSS |
| **Backend API** | FastAPI, Pydantic, SQLAlchemy, aiosqlite |
| **Agent Runtime** | LangGraph, LangChain Core |
| **Storage** | SQLite (structured data), Qdrant (vector memory) |
| **Local LLM** | LM Studio (OpenAI-compatible API) |
| **Package Manager** | pnpm (monorepo) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Desktop App                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐│
│  │   React UI  │  │  Zustand    │  │  Tauri (Rust) Backend    ││
│  └──────┬──────┘  └─────────────┘  └────────────┬──────────────┘│
│         │                                       │               │
│         └─────────────── HTTP ────────────────┘               │
│                            │                                   │
└────────────────────────────┼───────────────────────────────────┘
                             │
┌────────────────────────────┼───────────────────────────────────┐
│                        Backend API                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  FastAPI    │  │   Agent     │  │      Memory Service     │ │
│  │  Routes    │  │  (LangGraph)│  │  (Qdrant + SQLite)      │ │
│  └──────┬──────┘  └──────┬──────┘  └────────────┬────────────┘ │
│         │                │                      │              │
│         └────────────────┼──────────────────────┘              │
│                          │                                     │
│  ┌──────────────────────┼──────────────────────────────────┐ │
│  │               Tool Registry & Executor                    │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐ │ │
│  │  │Web Tools│ │File Ops │ │ Shell   │ │ Memory Tools    │ │ │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    LM Studio (Local LLM)                   │ │
│  │              OpenAI-compatible API @ localhost             │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Flow

1. **Request Classification** — Fast-path for casual conversation, full agent for complex tasks
2. **Memory Retrieval** — Search Qdrant for relevant context + SQLite for conversation history
3. **Planning** — LLM decides: direct answer or tool execution
4. **Tool Execution** — File operations, web search, calculations (with optional approval)
5. **Response Synthesis** — Generate final answer with tool observations

## Project Structure

```
serviq/
├── apps/
│   └── desktop/              # Tauri + React desktop application
│       ├── src/              # React frontend source
│       │   ├── components/   # UI components
│       │   ├── hooks/         # Custom React hooks
│       │   └── lib/           # API utilities
│       └── src-tauri/         # Rust Tauri backend
│
├── backend/                   # FastAPI Python backend
│   ├── api/routes/           # API endpoints
│   ├── agent/               # Agent implementation (LangGraph)
│   ├── core/                # Config, logging, middleware
│   ├── db/                  # Database initialization
│   ├── llm/                 # LM Studio client
│   ├── memory/              # Memory service (Qdrant + SQLite)
│   ├── tools/               # Agent tools (web, file, shell)
│   ├── schemas/             # Pydantic models
│   └── services/            # Business logic services
│
├── docker/                    # Docker configs (Qdrant)
├── scripts/                  # Development utilities
├── workspace/                # Runtime workspace (gitignored)
│   ├── notes/               # User notes
│   ├── projects/           # Project files
│   └── serviq.sqlite3      # SQLite database
│
├── docker-compose.yml        # Qdrant container
├── package.json              # pnpm workspace config
└── .env                      # Environment configuration
```

## Getting Started

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Node.js](https://nodejs.org/) | v18+ | Frontend development |
| [pnpm](https://pnpm.io/) | v8+ | Monorepo package manager |
| [Python](https://python.org/) | 3.12 | Backend runtime |
| [Docker](https://docker.com/) | Latest | Qdrant vector database |
| [LM Studio](https://lmstudio.ai/) | Latest | Local LLM inference |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/cRED-f/serviq.git
cd serviq

# 2. Install frontend dependencies
pnpm install

# 3. Install backend dependencies (creates backend/.venv)
pnpm backend:install

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings (see Configuration below)

# 5. Start LM Studio
# - Download a model (recommended: Qwen2.5, Llama3, Mistral)
# - Start the HTTP server (default: http://localhost:1234)
```

## Configuration

Create a `.env` file in the repository root with the following settings:

### Application Settings

```env
# Server
SERVIQ_ENVIRONMENT=development
SERVIQ_API_HOST=127.0.0.1
SERVIQ_API_PORT=8787

# Security
LOCAL_API_TOKEN=your-secure-token
ENCRYPTION_KEY=your-32-character-encryption-key
```

### LM Studio Configuration

```env
# LM Studio (OpenAI-compatible API)
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_API_KEY=lm-studio
LMSTUDIO_TIMEOUT_SECONDS=120
LMSTUDIO_DEFAULT_CHAT_MODEL=qwen2.5-3b
```

### Database Configuration

```env
# SQLite (conversation store)
DATABASE_URL=sqlite+aiosqlite:///workspace/serviq.sqlite3

# Qdrant (vector memory)
QDRANT_URL=http://127.0.0.1:6333
QDRANT_COLLECTION=serviq_memory
```

### Workspace Configuration

```env
WORKSPACE_DIR=workspace
UPLOADS_DIR=workspace/uploads
GENERATED_DIR=workspace/generated
```

## API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/api/health` | Basic health check |
| `GET` | `/api/health/deep` | Deep health (includes DB) |
| `POST` | `/api/agent/run` | Run agent with full context |
| `GET` | `/api/llm/models` | List available LM Studio models |
| `POST` | `/api/llm/chat` | Chat completion |
| `POST` | `/api/llm/embeddings` | Generate embeddings |

### Tool Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tools` | List available tools |
| `POST` | `/api/tools/execute` | Execute a tool |
| `POST` | `/api/tools/{id}/approve` | Approve tool execution |
| `POST` | `/api/tools/{id}/reject` | Reject tool execution |

### Memory Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/memory` | List memory items |
| `POST` | `/api/memory` | Save to memory |
| `DELETE` | `/api/memory/{id}` | Delete memory item |

For full API documentation, see the FastAPI Swagger UI at `http://127.0.0.1:8787/docs` when the backend is running.

## Running the Application

### Step 1: Start Qdrant

```bash
# Using pnpm
pnpm qdrant:up

# Or directly with Docker
docker compose up -d qdrant
```

### Step 2: Start LM Studio

1. Open LM Studio
2. Download and load a model (e.g., Qwen2.5-3B-Instruct-Q4_K_M)
3. Start the HTTP server (Server → Start Server)

### Step 3: Start Backend

```bash
pnpm backend:dev
```

The backend runs at `http://127.0.0.1:8787`

### Step 4: Start Desktop App

```bash
pnpm desktop:dev
```

The desktop app will open with the Tauri dev window.

## Development Scripts

| Command | Description |
|---------|-------------|
| `pnpm desktop:dev` | Start Tauri desktop app in dev mode |
| `pnpm desktop:build` | Build production desktop app |
| `pnpm frontend:dev` | Run React frontend only (no Tauri) |
| `pnpm backend:dev` | Start FastAPI backend in dev mode |
| `pnpm backend:install` | Create venv and install Python dependencies |
| `pnpm backend:check` | Run backend health check |
| `pnpm qdrant:up` | Start Qdrant container |
| `pnpm qdrant:down` | Stop Qdrant container |
| `pnpm doctor` | Verify all dependencies and services |

## Troubleshooting

### LM Studio Connection Issues

```
Error: Could not connect to LM Studio
```

**Solutions:**
1. Ensure LM Studio is running with HTTP server enabled
2. Check the `LMSTUDIO_BASE_URL` in `.env` (default: `http://127.0.0.1:1234/v1`)
3. Verify the model is loaded and ready in LM Studio

### Qdrant Connection Issues

```
Error: Connection refused to Qdrant
```

**Solutions:**
1. Ensure Docker is running
2. Run `pnpm qdrant:up` to start the container
3. Check Qdrant is accessible at `http://127.0.0.1:6333`

### Tool Execution Blocked

```
Error: Tool requires approval before execution
```

**Solution:** This is expected behavior for high-risk tools (file write, shell commands). Approve in the Approval Layer panel in the desktop app, or adjust tool risk levels in `backend/services/tool_settings_store.py`.

### Port Already in Use

```
Error: [Errno 98] Address already in use
```

**Solutions:**
1. Check for other services using port 8787 (backend) or 1234 (LM Studio)
2. Update `SERVIQ_API_PORT` or `LMSTUDIO_BASE_URL` in `.env`

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ using FastAPI, LangGraph, Tauri, and React
</p>