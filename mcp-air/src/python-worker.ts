// persistent JSONL bridge to src/adapters/air_worker.py.
// stdout of the python child is JSONL-only; all diagnostics go to stderr on both sides (§12.3).
// This is a scaffold: process spawn/lifecycle, request correlation, and a single restart budget.
// It is NOT wired as the MCP main yet — python -m adapters.mcp_sdk_server stays production entrypoint.
import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import * as readline from "node:readline";

export interface ToolResultEnvelope {
  requestId: string;
  result: Record<string, unknown>;
}

export class PythonWorker {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private rl: readline.Interface | null = null;
  private pending = new Map<string, {
    resolve: (value: ToolResultEnvelope) => void;
    reject: (reason: Error) => void;
    timer: NodeJS.Timeout;
  }>();
  private restarted = false;

  constructor(
    private readonly command: string,
    private readonly args: string[],
    private readonly timeoutMs = 30000,
  ) {}

  private ensureStarted(): ChildProcessWithoutNullStreams {
    if (this.proc && !this.proc.killed) return this.proc;
    const proc = spawn(this.command, this.args, { stdio: ["pipe", "pipe", "pipe"] });
    proc.stderr.on("data", (chunk) => process.stderr.write(`[python-worker] ${chunk}`));
    const rl = readline.createInterface({ input: proc.stdout });
    rl.on("line", (line) => this.onLine(line));
    proc.once("exit", (code, signal) => {
      if (this.proc === proc) { this.proc = null; this.rl = null; }
      const error = new Error(`python-worker exited (code=${code}, signal=${signal})`);
      for (const entry of this.pending.values()) {
        clearTimeout(entry.timer);
        entry.reject(error);
      }
      this.pending.clear();
    });
    this.proc = proc;
    this.rl = rl;
    return proc;
  }

  private onLine(line: string): void {
    if (!line.trim()) return;
    let parsed: ToolResultEnvelope;
    try {
      parsed = JSON.parse(line);
    } catch {
      process.stderr.write(`[python-worker] malformed response line ignored\n`);
      return;
    }
    const entry = this.pending.get(parsed.requestId);
    if (entry) {
      this.pending.delete(parsed.requestId);
      clearTimeout(entry.timer);
      this.restarted = false; // a healthy response restores the one-restart budget
      entry.resolve(parsed);
    }
  }

  // Air generic retry plugins must NOT wrap this call for nl2sql — the single-retry budget
  // lives inside SqlService (§correction), not here.
  async call(tool: string, params: Record<string, unknown>): Promise<ToolResultEnvelope> {
    const proc = this.ensureStarted();
    const requestId = randomUUID();
    const line = JSON.stringify({ requestId, tool, params }) + "\n";

    return new Promise<ToolResultEnvelope>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(requestId);
        reject(new Error(`python-worker timeout after ${this.timeoutMs}ms`));
      }, this.timeoutMs);

      this.pending.set(requestId, { resolve, reject, timer });

      proc.stdin.write(line, (err) => {
        if (err) {
          clearTimeout(timer);
          this.pending.delete(requestId);
          reject(err);
        }
      });
    });
  }

  restartOnce(): void {
    if (this.restarted) throw new Error("python-worker already restarted once; giving up");
    this.restarted = true;
    this.proc?.kill();
    this.proc = null;
    this.rl?.close();
    this.rl = null;
  }

  close(): void {
    const error = new Error("python-worker closed");
    for (const entry of this.pending.values()) {
      clearTimeout(entry.timer);
      entry.reject(error);
    }
    this.pending.clear();
    this.proc?.stdin.end();
    this.proc?.kill();
    this.proc = null;
    this.rl?.close();
    this.rl = null;
  }
}
