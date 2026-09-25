// Claude-backed stand-in for the `@github/copilot-sdk/extension` API used by
// the Football Event Review extension. `joinSession` returns a session whose
// `send` runs a Claude agent (Claude Agent SDK) in the repository, and the
// Canvas actions are exposed to that agent as in-process MCP tools.
import { randomUUID } from "node:crypto";

import {
  createSdkMcpServer,
  query,
  tool,
} from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

export class CanvasError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
    this.name = "CanvasError";
  }
}

export function createCanvas(definition) {
  return definition;
}

// Shared with host.mjs: the repository root, the registered canvases, and the
// instance ID of the open Canvas that agent tool calls act on.
export const host = {
  repoRoot: process.cwd(),
  canvases: [],
  instanceId: "",
};

const SHELL_TOOLS = new Set(["Bash", "PowerShell"]);
const READ_ONLY_ACTIONS = new Set(["get_review_status"]);

function log(line) {
  console.log(`[claude-review-host ${new Date().toISOString()}] ${line}`);
}

function firstLine(text, limit = 160) {
  const line = String(text || "").trim().split("\n")[0];
  return line.length > limit ? `${line.slice(0, limit)}…` : line;
}

function actionInputShape(schema) {
  if (schema?.type !== "object" || !schema.properties) return {};
  try {
    return z.fromJSONSchema(schema).shape;
  } catch {
    // Keep every declared field available when a schema cannot be converted;
    // the action handler still validates its own input.
    return Object.fromEntries(
      Object.keys(schema.properties).map((key) => [key, z.any().optional()]),
    );
  }
}

function canvasToolServer(canvas, onActionCompleted) {
  return createSdkMcpServer({
    name: canvas.id,
    version: "1.0.0",
    tools: (canvas.actions || []).map((action) => tool(
      action.name,
      action.description || action.name,
      actionInputShape(action.inputSchema),
      async (args) => {
        try {
          const result = await action.handler({
            input: args || {},
            instanceId: host.instanceId,
          });
          onActionCompleted(action.name);
          return {
            content: [{type: "text", text: JSON.stringify(result ?? null)}],
          };
        } catch (error) {
          const code = error?.code ? `${error.code}: ` : "";
          return {
            content: [{type: "text", text: `${code}${error?.message}`}],
            isError: true,
          };
        }
      },
      {alwaysLoad: true},
    )),
  });
}

function systemPromptAppend(canvas) {
  return [
    `You are the review agent for the ${canvas.displayName || canvas.id} `
      + "Canvas. You run through the Claude review host in place of GitHub "
      + "Copilot, so wherever a request says Copilot, it means you.",
    `Canvas actions are tools on the \`${canvas.id}\` MCP server. An `
      + `instruction to call the \`${canvas.id} <action>\` canvas action means `
      + `call the tool \`mcp__${canvas.id}__<action>\`.`,
    "Finish every request by calling the reporting action that the request "
      + "names, such as publish_review_response. The Canvas shows the request "
      + "as working until you do.",
    "Follow CLAUDE.md and AGENTS.md in this repository.",
  ].join("\n");
}

class ClaudeReviewSession {
  constructor(options) {
    this.sessionId = process.env.SESSION_ID || randomUUID();
    this.workspacePath = undefined;
    this.canvases = options.canvases || [];
    this.listeners = new Map();
    this.queue = Promise.resolve();
    this.claudeSessionId = null;
  }

  on(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(listener);
    return () => this.listeners.get(type)?.delete(listener);
  }

  emit(type, data) {
    for (const listener of this.listeners.get(type) || []) {
      try {
        listener({type, data});
      } catch (error) {
        log(`${type} listener failed: ${error.message}`);
      }
    }
  }

  // Like Copilot, accept the message at once and run it in the background.
  // Requests run one at a time in a single, resumed Claude conversation.
  async send(message) {
    const id = randomUUID();
    this.queue = this.queue
      .then(() => this.run(message))
      .catch((error) => log(`Request failed: ${error.message}`));
    return id;
  }

  async run({prompt, displayPrompt, agentMode}) {
    const canvas = this.canvases[0];
    // Claude's own `plan` mode also blocks the Canvas tools, so a Copilot plan
    // handover runs in `dontAsk` mode: read-only tools and the Canvas actions
    // are allowed and every other tool is denied.
    const readOnly = agentMode === "plan";
    const permissionMode = readOnly
      ? "dontAsk"
      : process.env.CLAUDE_REVIEW_AUTOPILOT_PERMISSION_MODE
        || "bypassPermissions";
    log(`Request (${agentMode || "default"} → ${permissionMode}): `
      + firstLine(displayPrompt || prompt));

    let reported = false;
    let lastText = "";
    const onActionCompleted = (action) => {
      if (!READ_ONLY_ACTIONS.has(action)) reported = true;
    };
    try {
      const run = query({
        prompt,
        options: {
          cwd: host.repoRoot,
          resume: this.claudeSessionId || undefined,
          permissionMode,
          allowDangerouslySkipPermissions:
            permissionMode === "bypassPermissions",
          allowedTools: readOnly
            ? ["Read", "Glob", "Grep", `mcp__${canvas.id}`]
            : undefined,
          mcpServers: {
            [canvas.id]: canvasToolServer(canvas, onActionCompleted),
          },
          systemPrompt: {
            type: "preset",
            preset: "claude_code",
            append: systemPromptAppend(canvas),
          },
          model: process.env.CLAUDE_REVIEW_MODEL || undefined,
        },
      });
      for await (const message of run) {
        if (message.session_id) this.claudeSessionId = message.session_id;
        if (message.type === "assistant") {
          for (const block of message.message?.content || []) {
            if (block.type === "text" && !message.parent_tool_use_id) {
              lastText = block.text;
            }
            if (block.type !== "tool_use") continue;
            const prefix = `mcp__${canvas.id}__`;
            if (block.name.startsWith(prefix)) {
              log(`Canvas action: ${block.name.slice(prefix.length)}`);
            } else {
              log(`Tool: ${block.name}`);
            }
            // The extension shows "Updating or verifying the rules engine"
            // for shell tools; Copilot names its shell tool "powershell".
            this.emit("tool.execution_start", {
              toolName: SHELL_TOOLS.has(block.name) ? "powershell" : block.name,
            });
          }
        }
        if (message.type === "result") {
          log(`Result: ${message.subtype}, ${message.num_turns} turns, `
            + `$${Number(message.total_cost_usd || 0).toFixed(2)}`);
          if (message.is_error) {
            throw new Error(
              `Claude stopped (${message.subtype}): `
              + firstLine(message.result || lastText, 300),
            );
          }
        }
      }
      if (!reported) {
        // The extension ignores this when the request already finished.
        this.emit("session.error", {
          message: "Claude finished without reporting back to the Canvas. "
            + `Last reply: ${firstLine(lastText, 300)}`,
        });
      }
    } catch (error) {
      log(`Error: ${error.message}`);
      this.emit("session.error", {message: error.message});
    }
  }
}

export async function joinSession(options = {}) {
  host.canvases = options.canvases || [];
  return new ClaudeReviewSession(options);
}
