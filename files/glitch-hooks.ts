/**
 * glitch-hooks — the Glitch brain's Claude Code hooks, run under omp.
 *
 * The starter pack installs this in ~/.omp/agent/extensions/, so it loads in every omp session
 * and does nothing outside a Glitch folder. Every hook in Glitch's .claude/settings.json runs on
 * the matching omp event with Claude-shaped stdin, and its stdout envelope is applied the way
 * Claude Code would:
 *
 *   PreToolUse       write-guard.py            bash / edit / write / ast_edit
 *   PreToolUse       read-guard.py             read / grep / glob
 *   PostToolUse      post-tool-secret-guard.py bash output
 *   SessionStart     session-start-context.py  startup / resume / clear / compact
 *   UserPromptSubmit user-prompt-context.py    typed prompts
 *   SessionEnd       session-end-flush.py      exit, /new, /resume, /fork
 *   PreCompact       pre-compact-flush.py      before compaction
 *
 * The outputStyle ("Glitch", generated from SOUL.md) rides on the system prompt, as under Claude.
 * The flush hooks read a Claude-shaped transcript, written from the omp session to
 * ~/.omp/agent/glitch/transcripts/<session>.jsonl (the staged stub keeps pointing at it).
 * The engine is never touched: all logic stays in Glitch's own scripts.
 */
import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@oh-my-pi/pi-coding-agent";

const TRANSCRIPT_DIR = path.join(os.homedir(), ".omp", "agent", "glitch", "transcripts");
const GUARD_TIMEOUT_MS = 10_000;
const SESSION_START_TIMEOUT_MS = 30_000;
const URL_RE = /^[a-z][a-z0-9+.-]*:\/\//i;

type HookOutput = {
	permissionDecision?: "allow" | "deny" | "ask";
	permissionDecisionReason?: string;
	additionalContext?: string;
};

type ToolCallResult = { block: true; reason: string } | { additionalContext: string } | undefined;

/** The Glitch root holding cwd, or undefined outside a Glitch brain. */
function glitchRoot(cwd: string): string | undefined {
	for (let dir = path.resolve(cwd); ; dir = path.dirname(dir)) {
		if (fs.existsSync(path.join(dir, ".claude", "hooks", "write-guard.py"))) return dir;
		if (path.dirname(dir) === dir) return undefined;
	}
}

function hookCommand(root: string, script: string): string[] {
	return [
		"uv",
		"run",
		"--no-project",
		"--directory",
		path.join(root, ".claude", "scripts"),
		"python",
		path.join(root, ".claude", "hooks", script),
	];
}

/** Runs one hook with JSON on stdin; returns its hookSpecificOutput, or undefined for silence. */
async function runHook(
	root: string,
	script: string,
	payload: Record<string, unknown>,
	timeoutMs: number,
): Promise<HookOutput | undefined> {
	const proc = Bun.spawn(hookCommand(root, script), {
		cwd: root,
		stdin: new Blob([JSON.stringify(payload)]),
		stdout: "pipe",
		stderr: "ignore",
		env: { ...process.env, CLAUDE_PROJECT_DIR: root },
	});
	const timer = setTimeout(() => {
		try {
			proc.kill();
		} catch {}
	}, timeoutMs);
	try {
		const stdout = (await new Response(proc.stdout).text()).trim();
		await proc.exited;
		if (!stdout) return undefined;
		const parsed = JSON.parse(stdout) as { hookSpecificOutput?: HookOutput };
		return parsed.hookSpecificOutput;
	} catch {
		return undefined;
	} finally {
		clearTimeout(timer);
	}
}

/** Starts a hook that must outlive this process (session end); fire and forget. */
function runHookDetached(root: string, script: string, payload: Record<string, unknown>): void {
	const [cmd, ...args] = hookCommand(root, script);
	const child = spawn(cmd, args, {
		cwd: root,
		detached: true,
		stdio: ["pipe", "ignore", "ignore"],
		env: { ...process.env, CLAUDE_PROJECT_DIR: root },
	});
	child.on("error", () => {});
	child.stdin?.end(JSON.stringify(payload));
	child.unref();
}

/** A tool path as a filesystem path: undefined for URLs, read selectors (`:50-80`, `?q=`) stripped. */
function fsPath(raw: string, cwd: string): string | undefined {
	const trimmed = raw.trim();
	if (!trimmed || URL_RE.test(trimmed)) return undefined;
	let candidate = path.resolve(cwd, trimmed.split("?")[0]);
	while (!fs.existsSync(candidate)) {
		const colon = candidate.lastIndexOf(":");
		if (colon <= candidate.lastIndexOf(path.sep)) break;
		candidate = candidate.slice(0, colon);
	}
	return candidate;
}

/** `;`-separated grep/glob path lists, minus `!` excludes. */
function pathList(value: unknown): string[] {
	if (typeof value !== "string" || !value.trim()) return ["."];
	return value
		.split(";")
		.map(p => p.trim())
		.filter(p => p && !p.startsWith("!"));
}

function textOf(content: unknown): string[] {
	if (typeof content === "string") return content.trim() ? [content] : [];
	if (!Array.isArray(content)) return [];
	return content
		.filter((b): b is { type: "text"; text: string } => b?.type === "text" && typeof b.text === "string")
		.map(b => b.text)
		.filter(t => t.trim());
}

/** Claude-shaped JSONL (user/assistant text only) for the flush hooks and /digest's ClaudeAdapter. */
function writeTranscript(sessionId: string, entries: readonly unknown[]): string | undefined {
	const lines: string[] = [];
	for (const entry of entries as { type?: string; id?: string; timestamp?: string; message?: { role?: string; content?: unknown } }[]) {
		if (entry?.type !== "message") continue;
		const role = entry.message?.role;
		if (role !== "user" && role !== "assistant") continue;
		const texts = textOf(entry.message?.content);
		if (!texts.length) continue;
		lines.push(
			JSON.stringify({
				type: role,
				uuid: entry.id,
				sessionId,
				timestamp: entry.timestamp,
				message: { role, content: texts.map(text => ({ type: "text", text })) },
			}),
		);
	}
	if (!lines.length) return undefined;
	fs.mkdirSync(TRANSCRIPT_DIR, { recursive: true });
	const file = path.join(TRANSCRIPT_DIR, `${sessionId}.jsonl`);
	fs.writeFileSync(file, `${lines.join("\n")}\n`);
	return file;
}

/** The Glitch output style body (SOUL.md's persona), frontmatter stripped. */
function outputStyle(root: string): string | undefined {
	try {
		const text = fs.readFileSync(path.join(root, ".claude", "output-styles", "glitch.md"), "utf8");
		return text.replace(/^---\n[\s\S]*?\n---\n/, "").trim() || undefined;
	} catch {
		return undefined;
	}
}

function isMain(ctx: ExtensionContext): boolean {
	return ctx.agent?.kind !== "sub";
}

/** Applies a PreToolUse envelope: deny blocks, ask goes to the user, context rides along. */
async function applyDecision(out: HookOutput | undefined, ctx: ExtensionContext): Promise<ToolCallResult> {
	if (!out) return undefined;
	const reason = out.permissionDecisionReason?.trim() ?? "";
	const context = out.additionalContext?.trim() ?? "";
	if (out.permissionDecision === "deny") {
		return { block: true, reason: [reason || "Blocked by Glitch", context].filter(Boolean).join("\n\n") };
	}
	if (out.permissionDecision === "ask") {
		const ok = ctx.hasUI && (await ctx.ui.confirm("Glitch", reason || "Allow this?"));
		if (!ok) return { block: true, reason: reason ? `Not approved: ${reason}` : "Not approved" };
	}
	return context ? { additionalContext: context } : undefined;
}

export default function glitchHooks(pi: ExtensionAPI) {
	let pendingStart: Promise<string | undefined> | undefined;
	const pendingPrompt: string[] = [];

	const base = (ctx: ExtensionContext) => {
		const event: Record<string, unknown> = { session_id: ctx.sessionManager.getSessionId(), cwd: ctx.cwd };
		if (!isMain(ctx)) event.agent_id = ctx.agent?.id;
		return event;
	};

	const queueSessionStart = (ctx: ExtensionContext, source: "startup" | "resume" | "clear" | "compact") => {
		const root = glitchRoot(ctx.cwd);
		if (!root || !isMain(ctx)) return;
		pendingStart = runHook(
			root,
			"session-start-context.py",
			{ ...base(ctx), hook_event_name: "SessionStart", source },
			SESSION_START_TIMEOUT_MS,
		).then(out => out?.additionalContext?.trim() || undefined);
	};

	const flush = (
		ctx: ExtensionContext,
		script: "session-end-flush.py" | "pre-compact-flush.py",
		fields: Record<string, string>,
		entries: readonly unknown[],
	) => {
		const root = glitchRoot(ctx.cwd);
		if (!root || !isMain(ctx)) return;
		const sessionId = ctx.sessionManager.getSessionId();
		const transcript = writeTranscript(sessionId, entries);
		if (!transcript) return;
		runHookDetached(root, script, { session_id: sessionId, cwd: ctx.cwd, transcript_path: transcript, ...fields });
	};

	// ── SessionStart ──────────────────────────────────────────────────────────────────────────
	pi.on("session_start", (_event, ctx) => {
		const resumed = ctx.sessionManager.getBranch().some(e => e.type === "message");
		queueSessionStart(ctx, resumed ? "resume" : "startup");
	});
	pi.on("session_switch", (event, ctx) => queueSessionStart(ctx, event.reason === "new" ? "clear" : "resume"));
	pi.on("session_compact", (_event, ctx) => queueSessionStart(ctx, "compact"));

	// ── UserPromptSubmit ──────────────────────────────────────────────────────────────────────
	pi.on("input", async (event, ctx) => {
		const root = glitchRoot(ctx.cwd);
		if (!root || !isMain(ctx) || event.source === "extension") return;
		const out = await runHook(
			root,
			"user-prompt-context.py",
			{ ...base(ctx), hook_event_name: "UserPromptSubmit", prompt: event.text },
			GUARD_TIMEOUT_MS,
		);
		const context = out?.additionalContext?.trim();
		if (context) pendingPrompt.push(context);
	});

	// Both context hooks land with the next prompt; the persona sits on the system prompt.
	pi.on("before_agent_start", async (event, ctx) => {
		const root = glitchRoot(ctx.cwd);
		if (!root || !isMain(ctx) || event.reason !== "prompt") return;
		const start = pendingStart ? await pendingStart : undefined;
		pendingStart = undefined;
		const parts = [start, ...pendingPrompt.splice(0)].filter((p): p is string => !!p);
		const persona = outputStyle(root);
		return {
			systemPrompt: persona ? [...event.systemPrompt, persona] : undefined,
			message: parts.length
				? { customType: "glitch-context", content: parts.join("\n\n---\n\n"), display: false }
				: undefined,
		};
	});

	// ── PreToolUse ────────────────────────────────────────────────────────────────────────────
	pi.on("tool_call", async (event, ctx) => {
		const root = glitchRoot(ctx.cwd);
		if (!root) return;
		const input = event.input as Record<string, unknown>;
		const guard = (script: string, toolName: string, toolInput: Record<string, unknown>, cwd = ctx.cwd) =>
			runHook(
				root,
				script,
				{ ...base(ctx), cwd, hook_event_name: "PreToolUse", tool_name: toolName, tool_input: toolInput },
				GUARD_TIMEOUT_MS,
			);

		switch (event.toolName) {
			case "bash": {
				const command = input.command;
				if (typeof command !== "string") return;
				const cwd = typeof input.cwd === "string" ? path.resolve(ctx.cwd, input.cwd) : ctx.cwd;
				return applyDecision(await guard("write-guard.py", "Bash", { command }, cwd), ctx);
			}
			case "write":
			case "edit":
			case "ast_edit": {
				const raw = Array.isArray(input.paths) ? input.paths : [input.path];
				const content =
					typeof input.content === "string"
						? input.content
						: typeof input.input === "string"
							? input.input
							: JSON.stringify(input);
				const context: string[] = [];
				for (const p of raw) {
					const file = typeof p === "string" ? fsPath(p, ctx.cwd) : undefined;
					if (!file) continue;
					const toolInput =
						event.toolName === "write" ? { file_path: file, content } : { file_path: file, new_string: content };
					const result = await applyDecision(
						await guard("write-guard.py", event.toolName === "write" ? "Write" : "Edit", toolInput),
						ctx,
					);
					if (result && "block" in result) return result;
					if (result) context.push(result.additionalContext);
				}
				return context.length ? { additionalContext: context.join("\n\n") } : undefined;
			}
			case "read":
			case "grep":
			case "glob": {
				const targets = event.toolName === "read" ? [input.path] : pathList(input.path);
				const context: string[] = [];
				for (const t of targets) {
					const p = typeof t === "string" ? fsPath(t, ctx.cwd) : undefined;
					if (!p) continue;
					const toolInput =
						event.toolName === "glob"
							? { pattern: p }
							: event.toolName === "grep"
								? { path: p, pattern: input.pattern }
								: { file_path: p };
					const name = event.toolName === "glob" ? "Glob" : event.toolName === "grep" ? "Grep" : "Read";
					const result = await applyDecision(await guard("read-guard.py", name, toolInput), ctx);
					if (result && "block" in result) return result;
					if (result) context.push(result.additionalContext);
				}
				return context.length ? { additionalContext: context.join("\n\n") } : undefined;
			}
		}
	});

	// ── PostToolUse ───────────────────────────────────────────────────────────────────────────
	pi.on("tool_result", async (event, ctx) => {
		const root = glitchRoot(ctx.cwd);
		if (!root || event.toolName !== "bash") return;
		const stdout = textOf(event.content).join("\n");
		if (!stdout) return;
		const out = await runHook(
			root,
			"post-tool-secret-guard.py",
			{
				...base(ctx),
				hook_event_name: "PostToolUse",
				tool_name: "Bash",
				tool_input: { command: event.input.command },
				tool_response: { stdout },
			},
			GUARD_TIMEOUT_MS,
		);
		const context = out?.additionalContext?.trim();
		return context ? { additionalContext: context } : undefined;
	});

	// ── SessionEnd / PreCompact ───────────────────────────────────────────────────────────────
	pi.on("session_before_switch", (event, ctx) => {
		flush(ctx, "session-end-flush.py", { reason: event.reason === "new" ? "clear" : "other" }, ctx.sessionManager.getBranch());
	});
	pi.on("session_shutdown", (_event, ctx) => {
		flush(ctx, "session-end-flush.py", { reason: "prompt_input_exit" }, ctx.sessionManager.getBranch());
	});
	pi.on("session_before_compact", (event, ctx) => {
		flush(ctx, "pre-compact-flush.py", { trigger: "compact" }, event.branchEntries);
	});
}
