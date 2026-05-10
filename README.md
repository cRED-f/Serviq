# Serviq

**Serviq** is a local AI assistant designed for day to day tasks. It leverages the power of large language models running on your local machine via [LM Studio](https://lmstudio.ai/) and combines it with a robust backend and a sleek desktop interface.

The project is built with a focus on privacy, performance, and extensibility, allowing you to have a powerful AI companion that runs entirely on your own hardware.

## Features

- **Local First:** All your data and models are stored and processed locally. No need to send your code or conversations to a third-party service.
- **Bring Your Own Model:** Works with any model supported by LM Studio.
- **Rich Desktop App:** A cross-platform desktop application built with [Tauri](https://tauri.app/) and [React](https://react.dev/).
- **Powerful Backend:** A [FastAPI](https://fastapi.tiangolo.com/) backend that orchestrates the AI agent, memory, and tool usage.
- **Conversational Agent:** A sophisticated agent built with [LangGraph](https://langchain-ai.github.io/langgraph/) that can reason, use tools, and remember past interactions.
- **Long-Term Memory:** Utilizes [Qdrant](https://qdrant.tech/) for efficient vector-based long-term memory, allowing the agent to recall information from past conversations.
- **Tool Usage:** The agent can use a variety of tools to perform actions, such as searching the web, accessing files, and more.
- **Developer Focused:** Designed with developers in mind, providing a powerful and extensible platform for building custom AI-powered workflows.

## Architecture

Serviq is a monorepo managed with `pnpm`. The project is divided into two main components:

- `apps/desktop`: A [Tauri](https://tauri.app/) application that provides the user interface. It's built with [React](https://react.dev/), [Vite](https://vitejs.dev/), and [Tailwind CSS](https://tailwindcss.com/).
- `backend`: A [Python](https://www.python.org/) application built with [FastAPI](https://fastapi.tiangolo.com/) that serves the AI agent and API.

The backend uses [LangGraph](https://langchain-ai.github.io/langgraph/) to create a stateful, multi-step agent. The agent's logic is defined in `backend/agent/graph.py`. It communicates with a local LLM through [LM Studio](https://lmstudio.ai/).

For memory, Serviq uses a combination of [SQLite](https://www.sqlite.org/index.html) for structured data and [Qdrant](https://qdrant.tech/) for semantic vector search.

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/en/) (v18 or later)
- [pnpm](https://pnpm.io/installation)
- [Python](https://www.python.org/downloads/) (v3.11 or later)
- [Docker](https://www.docker.com/products/docker-desktop/)
- [LM Studio](https://lmstudio.ai/)

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/serviq.git
    cd serviq
    ```

2.  **Install frontend dependencies:**

    ```bash
    pnpm install
    ```

3.  **Install backend dependencies:**

    ```bash
    pnpm backend:install
    ```

4.  **Start LM Studio:**

    Open LM Studio, download a model, and start the local server.

### Running the Application

1.  **Start the Qdrant vector database:**

    ```bash
    docker compose up -d qdrant
    ```

2.  **Start the backend server:**

    ```bash
    pnpm backend:dev
    ```

3.  **Run the desktop application:**

    ```bash
    pnpm desktop:dev
    ```

## Development

The `package.json` file at the root of the project contains all the necessary scripts for development.

- `pnpm desktop:dev`: Starts the desktop app in development mode.
- `pnpm desktop:build`: Builds the desktop app for production.
- `pnpm frontend:dev`: Starts the frontend development server (Vite).
- `pnpm backend:dev`: Starts the backend server in development mode.
- `pnpm backend:install`: Installs backend dependencies.
- `pnpm backend:check`: Runs checks on the backend code.
- `pnpm qdrant:up`: Starts the Qdrant Docker container.
- `pnpm qdrant:down`: Stops the Qdrant Docker container.
- `pnpm doctor`: Checks if all the required dependencies and services are available.

## Contributing

Contributions are welcome! Please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
