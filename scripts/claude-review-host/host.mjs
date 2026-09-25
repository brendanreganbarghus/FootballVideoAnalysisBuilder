// Runs the Innovation Day Football Event Review Canvas with a Claude agent in
// place of GitHub Copilot.
//
// Usage: node host.mjs [--segment segment-0120-020]
import { randomUUID } from "node:crypto";
import { register } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

register("./hooks.mjs", import.meta.url);

function argument(name, fallback) {
  const index = process.argv.indexOf(`--${name}`);
  return index >= 0 && process.argv[index + 1]
    ? process.argv[index + 1]
    : fallback;
}

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..");
const segment = argument("segment", "segment-0120-020");
const localApp = "http://127.0.0.1:8080";

try {
  await fetch(`${localApp}/api/coordination/health`);
} catch {
  console.error(
    `The local app is not running at ${localApp}. Start it first:\n`
    + "  .\\.venv\\Scripts\\python .\\scripts\\serve-local.py "
    + "--bind 127.0.0.1 --port 8080",
  );
  process.exit(1);
}

// The extension derives its preferred Canvas port from SESSION_ID.
process.env.SESSION_ID ||= `claude-review-${randomUUID()}`;

const { host } = await import("./copilot-shim.mjs");
host.repoRoot = repoRoot;
await import(pathToFileURL(resolve(
  repoRoot, ".github", "extensions", "football-event-review", "extension.mjs",
)).href);

const canvas = host.canvases[0];
host.instanceId = randomUUID();
const opened = await canvas.open({
  instanceId: host.instanceId,
  input: {segment},
});

console.log(`${opened.title}: ${opened.status}`);
console.log(`Canvas:   ${opened.url}`);
console.log(`Launcher: ${localApp}/review-canvas?theme=innovation`);
console.log("Agent:    Claude (Claude Agent SDK). Press Ctrl+C to stop.");

let closing = false;
async function close() {
  if (closing) return;
  closing = true;
  await canvas.onClose?.({instanceId: host.instanceId}).catch(() => {});
  process.exit(0);
}
process.on("SIGINT", close);
process.on("SIGTERM", close);
