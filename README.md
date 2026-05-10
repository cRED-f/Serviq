# Serviq

**Serviq** is a local-first AI assistant for day-to-day tasks. It runs large language models on your own machine through [LM Studio](https://lmstudio.ai/) and pairs them with a FastAPI backend plus a cross-platform desktop app.

The focus is privacy and control: your models, data, and conversation history stay on your hardware while the agent keeps context with structured storage and semantic memory.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Development Scripts](#development-scripts)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Local First:** All your data and models are stored and processed locally.
- **Bring Your Own Model:** Works with any model supported by LM Studio.
- **Rich Desktop App:** A cross-platform desktop application built with [Tauri](https://tauri.app/) and [React](https://react.dev/).
- **Powerful Backend:** A [FastAPI](https://fastapi.tiangolo.com/) backend that orchestrates the AI agent, memory, and tool usage.
- **Conversational Agent:** A [LangGraph](https://langchain-ai.github.io/langgraph/) agent that can reason, use tools, and remember past interactions.
- **Long-Term Memory:** Uses [Qdrant](https://qdrant.tech/) for vector memory with [SQLite](https://www.sqlite.org/index.html) for structured data.
- **Tool Usage:** The agent can invoke tools to search, read files, and interact with the system.
- **Developer Focused:** Extensible architecture for building custom AI workflows.

## Tech Stack

- **Desktop UI:** Tauri, React, Vite, Tailwind CSS
- **Backend API:** FastAPI, Pydantic, SQLAlchemy
- **Agent Runtime:** LangGraph, LangChain core
- **Storage:** SQLite (structured), Qdrant (vector memory)
- **Local LLM:** LM Studio

## Architecture

Serviq is a `pnpm` monorepo with two main components:

- `apps/desktop`: Tauri + React desktop application.
- `backend`: FastAPI service hosting the agent, memory, and APIs.

The backend defines the agent graph in `backend/agent/graph.py`, connects to LM Studio for local inference, stores structured data in SQLite, and indexes semantic memory in Qdrant. The desktop app communicates with the backend over HTTP.

## Project Structure

- `apps/desktop`: Desktop UI (Tauri + React).
- `backend`: FastAPI service and agent runtime.
- `docker`: Local service assets (Qdrant storage).
- `scripts`: Helper scripts for backend setup and diagnostics.
- `.env.example`: Sample environment configuration.
- `docker-compose.yml`: Qdrant service definition.

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/en/) (v18 or later)
- [pnpm](https://pnpm.io/installation)
- [Python](https://www.python.org/downloads/) (v3.11 or later)
- [Docker](https://www.docker.com/products/docker-desktop/)
- [LM Studio](https://lmstudio.ai/)

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/cRED-f/serviq.git
   cd serviq
   ```

2. **Install frontend dependencies:**

   ```bash
   pnpm install
   ```

3. **Install backend dependencies (creates `backend/.venv`):**

   ```bash
   pnpm backend:install
   ```

4. **Start LM Studio:**

   Open LM Studio, download a model, and start the local server.

## Configuration

The backend reads environment settings from a `.env` file at the repository root. Use `.env.example` as a starting point.

Key settings include:

- **App:** `APP_HOST`, `APP_PORT`, `APP_CORS_ORIGINS`
- **Security:** `LOCAL_API_TOKEN`, `ENCRYPTION_KEY`
- **LM Studio:** `LM_STUDIO_BASE_URL`, `LM_STUDIO_DEFAULT_CHAT_MODEL`
- **Databases:** `SQLITE_DATABASE_URL`, `QDRANT_URL`, `QDRANT_COLLECTION`
- **Workspace:** `WORKSPACE_DIR`, `UPLOADS_DIR`, `GENERATED_DIR`

## Running the Application

1. **Start Qdrant:**

   ```bash
   docker compose up -d qdrant
   ```

2. **Start the backend server:**

   ```bash
   pnpm backend:dev
   ```

3. **Run the desktop application:**

   ```bash
   pnpm desktop:dev
   ```

## Development Scripts

The root `package.json` provides the main workflow scripts:

- `pnpm desktop:dev`: Start the desktop app (Tauri dev).
- `pnpm desktop:build`: Build the desktop app (Tauri build).
- `pnpm frontend:dev`: Start the Vite dev server only.
- `pnpm backend:dev`: Start the FastAPI backend in dev mode.
- `pnpm backend:install`: Create the backend virtual env and install dependencies.
- `pnpm backend:check`: Run the backend health check endpoint.
- `pnpm qdrant:up`: Start Qdrant.
- `pnpm qdrant:down`: Stop Qdrant.
- `pnpm doctor`: Verify required dependencies and services.

## Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
