import { spawnSync } from "node:child_process";

const isWindows = process.platform === "win32";

function check(label, command, args = []) {
  console.log(`\n${label}:`);
  const result = spawnSync(command, args, { stdio: "inherit", shell: isWindows });
  if (result.status !== 0) {
    console.log(`Not available or not running: ${command} ${args.join(" ")}`.trim());
  }
}

check("Python", isWindows ? "py" : "python3", isWindows ? ["-3", "--version"] : ["--version"]);
check("Node", "node", ["--version"]);
check("pnpm", "pnpm", ["--version"]);
check("Rust", "rustc", ["--version"]);
check("Cargo", "cargo", ["--version"]);
check("Docker", "docker", ["--version"]);
check("Qdrant health", "curl", ["-fsS", "http://localhost:6333/healthz"]);
check("LM Studio models endpoint", "curl", ["-fsS", "http://localhost:1234/v1/models"]);
