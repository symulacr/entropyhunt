import * as fs from "node:fs";
import { spawn, type ChildProcess } from "node:child_process";

export type SpawnedProcess = {
  label: string;
  command: string[];
  pid: number;
  child: ChildProcess;
  stdoutPath: string;
  stderrPath: string;
};

type SpawnManagedProcessArgs = {
  label: string;
  command: string[];
  cwd: string;
  env?: NodeJS.ProcessEnv;
  logDir: string;
  teeStdout?: boolean;
  teeStderr?: boolean;
  stdioMode?: "pipe" | "inherit";
};

function writeChunk(stream: fs.WriteStream, chunk: Buffer | string): void {
  stream.write(chunk);
}

export function spawnManagedProcess({
  label,
  command,
  cwd,
  env,
  logDir,
  teeStdout = false,
  teeStderr = false,
  stdioMode = "pipe",
}: SpawnManagedProcessArgs): SpawnedProcess {
  const [bin, ...args] = command;
  if (!bin) {
    throw new Error(`Cannot spawn ${label}: empty command`);
  }

  fs.mkdirSync(logDir, { recursive: true });
  const stdoutPath = `${logDir}/${label}.stdout.log`;
  const stderrPath = `${logDir}/${label}.stderr.log`;
  const stdoutStream = stdioMode === "pipe" ? fs.createWriteStream(stdoutPath, { flags: "a" }) : null;
  const stderrStream = stdioMode === "pipe" ? fs.createWriteStream(stderrPath, { flags: "a" }) : null;
  if (stdioMode === "inherit") {
    fs.writeFileSync(stdoutPath, `${label} attached directly to the controlling terminal; stdout is not captured in this log.\n`);
    fs.writeFileSync(stderrPath, `${label} attached directly to the controlling terminal; stderr is not captured in this log.\n`);
  }

  const child = spawn(bin, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: stdioMode === "inherit" ? ["inherit", "inherit", "inherit"] : ["ignore", "pipe", "pipe"],
    detached: stdioMode === "inherit" ? false : process.platform !== "win32",
  });

  if (stdioMode === "pipe") {
    child.stdout?.on("data", (chunk) => {
      if (stdoutStream) writeChunk(stdoutStream, chunk);
      if (teeStdout) process.stdout.write(chunk);
    });
    child.stderr?.on("data", (chunk) => {
      if (stderrStream) writeChunk(stderrStream, chunk);
      if (teeStderr) process.stderr.write(chunk);
    });
    child.once("close", () => {
      stdoutStream?.end();
      stderrStream?.end();
    });
  }

  const pid = child.pid ?? 0;
  if (!pid) {
    throw new Error(`Failed to spawn ${label}`);
  }

  return { label, command, pid, child, stdoutPath, stderrPath };
}

function killPidTree(pid: number, signal: NodeJS.Signals): void {
  if (pid <= 0) return;
  try {
    if (process.platform !== "win32") {
      process.kill(-pid, signal);
      return;
    }
  } catch {
    // fall through to direct child kill
  }
  try {
    process.kill(pid, signal);
  } catch {
    // ignore already-exited children
  }
}

export async function waitForExit(proc: SpawnedProcess): Promise<number> {
  if (typeof proc.child.exitCode === "number") {
    return proc.child.exitCode;
  }
  if (proc.child.signalCode) {
    return 128;
  }
  return await new Promise((resolve) => {
    proc.child.once("exit", (code, signal) => {
      if (typeof code === "number") {
        resolve(code);
        return;
      }
      resolve(signal ? 128 : 0);
    });
  });
}

export async function terminateManagedProcess(proc: SpawnedProcess, graceMs = 2_000): Promise<void> {
  if (proc.child.exitCode !== null || proc.child.signalCode !== null) {
    return;
  }

  killPidTree(proc.pid, "SIGTERM");
  const exited = await Promise.race([
    waitForExit(proc).then(() => true),
    new Promise<boolean>((resolve) => setTimeout(() => resolve(false), graceMs)),
  ]);
  if (exited) {
    return;
  }
  killPidTree(proc.pid, "SIGKILL");
  await waitForExit(proc);
}
