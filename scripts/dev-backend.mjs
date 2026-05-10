import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDir, "..");
const backendDir = join(projectRoot, "backend");
const isWindows = process.platform === "win32";

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd ?? backendDir,
    stdio: "inherit",
    shell: isWindows,
    env: { ...process.env, ...(options.env ?? {}) },
  });

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function tryCommand(command, args) {
  const result = spawnSync(command, args, {
    cwd: backendDir,
    stdio: "ignore",
    shell: isWindows,
  });
  return result.status === 0;
}

function detectPython() {
  const candidates = isWindows
    ? [["py", ["-3.12", "--version"]], ["py", ["-3", "--version"]], ["python", ["--version"]]]
    : [["python3.12", ["--version"]], ["python3", ["--version"]], ["python", ["--version"]]];

  for (const [command, args] of candidates) {
    if (tryCommand(command, args)) {
      return { command, createVenvArgs: command === "py" ? [args[0], "-m", "venv", ".venv"] : ["-m", "venv", ".venv"] };
    }
  }

  console.error("Python 3.12+ was not found. Install Python and try again.");
  process.exit(1);
}

function venvPythonPath() {
  return join(backendDir, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
}

const python = detectPython();

if (!existsSync(venvPythonPath())) {
  console.log("Backend virtual environment not found. Creating backend/.venv...");
  run(python.command, python.createVenvArgs);
}

const venvPython = venvPythonPath();

console.log("Installing backend dependencies...");
run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"]);
run(venvPython, ["-m", "pip", "install", "-e", ".[dev]"]);

console.log("Starting FastAPI backend at http://127.0.0.1:8787 ...");
run(venvPython, ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8787", "--reload"]);
