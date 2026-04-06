import { spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import { formatRuntimeHelp, parseRuntimeArgs, type RuntimeOptions } from "./config";
import { waitForRuntimeReady } from "./health";
import { findContiguousPortRange, findFreePort } from "./ports";
import { spawnManagedProcess, terminateManagedProcess, waitForExit, type SpawnedProcess } from "./processes";

type SessionManifest = {
  sessionName: string;
  sessionDir: string;
  status: "starting" | "ready" | "running" | "stopping" | "completed" | "failed" | "cancelled";
  startedAt: string;
  readyAt?: string;
  completedAt?: string;
  cwd: string;
  config: Record<string, unknown>;
  ports: {
    basePort: number;
    servePort: number;
  };
  paths: {
    outputDir: string;
    logDir: string;
    proofsPath: string;
    snapshotFile: string;
    snapshotUrl: string;
    launcherStdout: string;
    launcherStderr: string;
    monitorStdout?: string;
    monitorStderr?: string;
  };
  processes: {
    launcher?: { pid: number; command: string[] };
    monitor?: { pid: number; command: string[] };
  };
  exit?: {
    launcherCode?: number;
    monitorCode?: number;
  };
  error?: string;
};

function writeJson(filePath: string, payload: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`);
}

function wantsHelp(argv: string[]): boolean {
  return argv.includes("--help") || argv.includes("-h");
}

function emitStatus(message: string): void {
  process.stdout.write(`[hunt] ${message}\n`);
}

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'\\''`)}'`;
}

function normalizedExecPath(): string {
  return process.execPath.replace(/ \(deleted\)$/, "");
}

function commandAvailable(command: string, args: string[] = ["--help"]): boolean {
  const result = spawnSync(command, args, { stdio: "ignore" });
  return !(result.error && (result.error as NodeJS.ErrnoException).code === "ENOENT");
}

function requireCommand(command: string, args: string[] = ["--help"], message?: string): void {
  if (!commandAvailable(command, args)) {
    throw new Error(message ?? `Required command is not available: ${command}`);
  }
}

function requireFile(filePath: string, message?: string): void {
  if (!fs.existsSync(filePath)) {
    throw new Error(message ?? `Required file does not exist: ${filePath}`);
  }
}

function currentSessionPaths(sessionDir: string, snapshotHost: string, snapshotPort: number) {
  const logDir = path.join(sessionDir, "logs");
  const outputDir = path.join(sessionDir, "snapshots");
  const proofsPath = path.join(sessionDir, "proofs.jsonl");
  const snapshotFile = path.join(outputDir, "snapshot.json");
  const snapshotUrl = `http://${snapshotHost}:${snapshotPort}/snapshot.json`;
  return { logDir, outputDir, proofsPath, snapshotFile, snapshotUrl };
}

function shouldTeeLauncherOutput(options: RuntimeOptions): boolean {
  switch (options.launcherOutputMode) {
    case "show":
      return true;
    case "quiet":
      return false;
    default:
      return !options.monitor;
  }
}

function parseTarget(target: string): { x: number; y: number } {
  const [xRaw, yRaw] = target.split(",", 2);
  const x = Number(xRaw);
  const y = Number(yRaw);
  if (!Number.isInteger(x) || !Number.isInteger(y)) {
    throw new Error(`Invalid target coordinate: ${target}`);
  }
  return { x, y };
}

function buildPeerLauncherCommand(options: RuntimeOptions, basePort: number, servePort: number, outputDir: string, proofsPath: string): string[] {
  const tickDelaySeconds = options.tickDelaySeconds ?? (options.monitor ? options.tickSeconds : 0.1);
  return [
    options.pythonBin,
    options.launcherScript,
    "--count",
    String(options.count),
    "--base-port",
    String(basePort),
    "--duration",
    String(options.duration),
    "--grid",
    String(options.grid),
    "--tick-seconds",
    String(options.tickSeconds),
    "--tick-delay-seconds",
    String(tickDelaySeconds),
    "--target",
    options.target,
    "--fail",
    options.failDrone,
    "--fail-at",
    String(options.failAt),
    "--output-dir",
    outputDir,
    "--transport",
    options.transport,
    "--mqtt-host",
    options.mqttHost,
    "--mqtt-base-port",
    String(options.mqttBasePort),
    "--serve-host",
    options.serveHost,
    "--serve-port",
    String(servePort),
    "--proofs-path",
    proofsPath,
  ];
}

function buildRosHostLauncherCommand(options: RuntimeOptions, cwd: string, snapshotFile: string, snapshotHost: string, snapshotPort: number): string[] {
  const rosWorkspace = path.resolve(cwd, options.rosWorkspace);
  const target = parseTarget(options.target);
  const rosSetup = `/opt/ros/${options.rosDistro}/setup.bash`;
  const buildStep = options.rosAutoBuild ? "colcon build && " : "";
  const command = [
    "set -eo pipefail",
    `source ${shellQuote(rosSetup)}`,
    `cd ${shellQuote(rosWorkspace)}`,
    `${buildStep}source ${shellQuote(path.join(rosWorkspace, "install", "setup.bash"))}`,
    `exec ros2 launch ${shellQuote(options.rosPackage)} ${shellQuote(options.rosLaunchFile)} count:=${options.count} grid:=${options.grid} target_x:=${target.x} target_y:=${target.y} tick_seconds:=${options.tickSeconds} fail_drone:=${shellQuote(options.failDrone)} fail_at:=${options.failAt} snapshot_path:=${shellQuote(snapshotFile)} snapshot_host:=${shellQuote(snapshotHost)} snapshot_port:=${snapshotPort}`,
  ].join(" && ");
  return ["bash", "-lc", command];
}

function buildRosDockerLauncherCommand(options: RuntimeOptions, cwd: string, snapshotFile: string, hostPort: number): string[] {
  const target = parseTarget(options.target);
  const relSnapshot = path.relative(cwd, snapshotFile).split(path.sep).join("/");
  const workspacePath = path.posix.join("/workspace", options.rosWorkspace.replace(/\\/g, "/"));
  const containerSnapshotFile = path.posix.join("/workspace", relSnapshot);
  const buildStep = options.rosAutoBuild ? "colcon build && " : "";
  const launchScript = [
    "set -eo pipefail",
    `source /opt/ros/${options.rosDistro}/setup.bash`,
    `cd ${shellQuote(workspacePath)}`,
    `${buildStep}source ${shellQuote(path.posix.join(workspacePath, "install", "setup.bash"))}`,
    `exec ros2 launch ${shellQuote(options.rosPackage)} ${shellQuote(options.rosLaunchFile)} count:=${options.count} grid:=${options.grid} target_x:=${target.x} target_y:=${target.y} tick_seconds:=${options.tickSeconds} fail_drone:=${shellQuote(options.failDrone)} fail_at:=${options.failAt} snapshot_path:=${shellQuote(containerSnapshotFile)} snapshot_host:=0.0.0.0 snapshot_port:=${hostPort}`,
  ].join(" && ");
  return [
    "docker",
    "run",
    "--rm",
    "--init",
    "-p",
    `${hostPort}:${hostPort}`,
    "-v",
    `${cwd}:/workspace`,
    "-w",
    "/workspace",
    options.dockerImage,
    "/bin/bash",
    "-lc",
    launchScript,
  ];
}

function buildMonitorCommand(options: RuntimeOptions, cwd: string, snapshotUrl: string): string[] {
  const monitorBinary = options.monitorBinary ? path.resolve(cwd, options.monitorBinary) : null;
  if (monitorBinary && fs.existsSync(monitorBinary)) {
    return [monitorBinary, "--source", snapshotUrl];
  }
  const siblingMonitor = path.join(path.dirname(normalizedExecPath()), "entropyhunt-monitor");
  if (fs.existsSync(siblingMonitor)) {
    return [siblingMonitor, "--source", snapshotUrl];
  }
  const bunBin = normalizedExecPath();
  return [bunBin, options.monitorScript, "--source", snapshotUrl];
}

async function resolvePorts(options: RuntimeOptions): Promise<{ basePort: number; servePort: number }> {
  if (options.mode === "peer") {
    const basePort = options.basePort ?? (await findContiguousPortRange(options.serveHost, options.count));
    const servePort = options.servePort ?? (await findFreePort(options.serveHost));
    return { basePort, servePort };
  }
  const servePort = options.rosSnapshotPortExplicit && options.rosSnapshotPort > 0
    ? options.rosSnapshotPort
    : await findFreePort(options.rosSnapshotHost);
  return { basePort: 0, servePort };
}

function ensureRosDockerImage(options: RuntimeOptions, cwd: string): void {
  const inspect = spawnSync("docker", ["image", "inspect", options.dockerImage], { stdio: "ignore" });
  if (inspect.status === 0) {
    emitStatus(`using cached ROS Docker image ${options.dockerImage}`);
    return;
  }
  emitStatus(`building ROS Docker image ${options.dockerImage}`);
  const dockerfile = path.resolve(cwd, "docker", "ros2-humble.Dockerfile");
  requireFile(dockerfile, `ROS Dockerfile missing: ${dockerfile}`);
  const build = spawnSync("docker", ["build", "-t", options.dockerImage, "-f", dockerfile, cwd], { stdio: "inherit" });
  if (build.status !== 0) {
    throw new Error(`Failed to build Docker image ${options.dockerImage}`);
  }
}

function validateModeRequirements(options: RuntimeOptions, cwd: string): void {
  if (options.mode === "peer") {
    requireCommand(options.pythonBin, ["--version"], `Peer mode requires ${options.pythonBin} on PATH`);
    requireFile(path.resolve(cwd, options.launcherScript), `Peer launcher script missing: ${options.launcherScript}`);
    return;
  }

  if (options.rosRuntime === "host") {
    requireCommand("ros2", ["--help"], "ROS host mode requires 'ros2' on PATH");
    requireCommand("colcon", ["--help"], "ROS host mode requires 'colcon' on PATH");
    requireFile(`/opt/ros/${options.rosDistro}/setup.bash`, `ROS distro setup not found: /opt/ros/${options.rosDistro}/setup.bash`);
    requireFile(path.resolve(cwd, options.rosWorkspace, "src", options.rosPackage, "launch", options.rosLaunchFile), `ROS launch file missing: ${path.join(options.rosWorkspace, "src", options.rosPackage, "launch", options.rosLaunchFile)}`);
    return;
  }

  requireCommand("docker", ["--help"], "ROS docker mode requires 'docker' on PATH");
  requireFile(path.resolve(cwd, "docker", "ros2-humble.Dockerfile"), "ROS docker mode requires docker/ros2-humble.Dockerfile");
}

function createLauncherCommand(options: RuntimeOptions, cwd: string, basePort: number, servePort: number, outputDir: string, proofsPath: string, snapshotFile: string): string[] {
  if (options.mode === "peer") {
    return buildPeerLauncherCommand(options, basePort, servePort, outputDir, proofsPath);
  }
  if (options.rosRuntime === "docker") {
    ensureRosDockerImage(options, cwd);
    return buildRosDockerLauncherCommand(options, cwd, snapshotFile, servePort);
  }
  return buildRosHostLauncherCommand(options, cwd, snapshotFile, options.rosSnapshotHost, servePort);
}

async function main(): Promise<number> {
  const argv = process.argv.slice(2);
  if (wantsHelp(argv)) {
    process.stdout.write(`${formatRuntimeHelp()}\n`);
    return 0;
  }
  const options = parseRuntimeArgs(argv);
  const cwd = process.cwd();
  emitStatus(`starting ${options.mode}${options.mode === "ros2" ? `:${options.rosRuntime}` : ""} runtime`);
  validateModeRequirements(options, cwd);
  const sessionRoot = path.resolve(options.sessionRoot);
  const sessionDir = path.join(sessionRoot, options.sessionName);
  const { basePort, servePort } = await resolvePorts(options);
  const snapshotHost = options.mode === "peer" ? options.serveHost : options.rosSnapshotHost;
  const paths = currentSessionPaths(sessionDir, snapshotHost, servePort);
  const snapshotFile = options.mode === "ros2" && options.rosSnapshotPath
    ? path.resolve(cwd, options.rosSnapshotPath)
    : paths.snapshotFile;
  fs.mkdirSync(paths.logDir, { recursive: true });
  fs.mkdirSync(paths.outputDir, { recursive: true });

  const manifestPath = path.resolve("runtime", "session.json");
  const sessionManifestPath = path.join(sessionDir, "session.json");

  const launcherCommand = createLauncherCommand(options, cwd, basePort, servePort, paths.outputDir, paths.proofsPath, snapshotFile);
  const manifest: SessionManifest = {
    sessionName: options.sessionName,
    sessionDir,
    status: "starting",
    startedAt: new Date().toISOString(),
    cwd,
    config: {
      mode: options.mode,
      rosRuntime: options.rosRuntime,
      count: options.count,
      duration: options.duration,
      grid: options.grid,
      tickSeconds: options.tickSeconds,
      tickDelaySeconds: options.tickDelaySeconds ?? (options.monitor ? options.tickSeconds : 0.1),
      target: options.target,
      failDrone: options.failDrone,
      failAt: options.failAt,
      transport: options.transport,
      monitor: options.monitor,
      launcherOutputMode: options.launcherOutputMode,
      monitorHoldOpen: options.monitorHoldOpen,
      pythonBin: options.pythonBin,
      launcherScript: options.launcherScript,
      monitorScript: options.monitorScript,
      rosDistro: options.rosDistro,
      rosWorkspace: options.rosWorkspace,
      rosPackage: options.rosPackage,
      rosLaunchFile: options.rosLaunchFile,
      rosSnapshotHost: options.rosSnapshotHost,
      rosSnapshotPort: options.rosSnapshotPort,
      rosSnapshotPath: options.rosSnapshotPath,
      rosAutoBuild: options.rosAutoBuild,
      dockerImage: options.dockerImage,
    },
    ports: { basePort, servePort },
    paths: {
      outputDir: paths.outputDir,
      logDir: paths.logDir,
      proofsPath: paths.proofsPath,
      snapshotFile,
      snapshotUrl: paths.snapshotUrl,
      launcherStdout: path.join(paths.logDir, "launcher.stdout.log"),
      launcherStderr: path.join(paths.logDir, "launcher.stderr.log"),
    },
    processes: {},
    exit: {},
  };

  const persistManifest = () => {
    writeJson(sessionManifestPath, manifest);
    writeJson(manifestPath, manifest);
  };

  let launcher: SpawnedProcess | undefined;
  let monitor: SpawnedProcess | undefined;
  let shuttingDown = false;

  const showLauncherOutput = shouldTeeLauncherOutput(options);
  const interactiveMonitorMode = options.monitor && process.stdout.isTTY && !showLauncherOutput;
  let statusLineCount = 0;
  const emitRunStatus = (message: string) => {
    if (interactiveMonitorMode) {
      statusLineCount += 1;
    }
    emitStatus(message);
  };
  const clearRunStatus = () => {
    if (!interactiveMonitorMode || statusLineCount <= 0) return;
    for (let index = 0; index < statusLineCount; index += 1) {
      process.stdout.write("\x1b[1A\x1b[2K\r");
    }
    statusLineCount = 0;
  };
  const readinessTimeoutMs =
    options.mode === "ros2"
      ? Math.max(options.readinessTimeoutMs, options.rosAutoBuild ? 180_000 : 45_000)
      : options.readinessTimeoutMs;

  const printSessionSummary = (launcherCode?: number, monitorCode?: number) => {
    if (interactiveMonitorMode && launcherCode === 0 && (monitorCode === 0 || monitorCode === undefined)) {
      console.log(`[hunt] completed | session=${manifest.sessionName} | snapshot=${manifest.paths.snapshotUrl}`);
      return;
    }
    const summary = [
      `Entropy Hunt session: ${manifest.sessionName}`,
      `mode=${options.mode}${options.mode === "ros2" ? `:${options.rosRuntime}` : ""}`,
      `status=${manifest.status}`,
      `session=${manifest.sessionDir}`,
      `snapshot=${manifest.paths.snapshotUrl}`,
      `proofs=${manifest.paths.proofsPath}`,
      `launcher_log=${manifest.paths.launcherStdout}`,
    ];
    if (manifest.paths.monitorStdout) summary.push(`monitor_log=${manifest.paths.monitorStdout}`);
    if (typeof launcherCode === "number") summary.push(`launcher_exit=${launcherCode}`);
    if (typeof monitorCode === "number") summary.push(`monitor_exit=${monitorCode}`);
    const line = summary.join(" | ");
    if (launcherCode && launcherCode !== 0) {
      console.error(line);
      console.error(`See stderr log: ${manifest.paths.launcherStderr}`);
      return;
    }
    console.log(line);
  };

  const shutdown = async (reason: string) => {
    if (shuttingDown) return;
    shuttingDown = true;
    manifest.status = manifest.status === "failed" ? "failed" : "stopping";
    manifest.error = manifest.error ?? reason;
    persistManifest();
    const terminations: Promise<void>[] = [];
    if (monitor) terminations.push(terminateManagedProcess(monitor));
    if (launcher) terminations.push(terminateManagedProcess(launcher));
    await Promise.allSettled(terminations);
  };

  const signalHandler = (signal: NodeJS.Signals) => {
    void shutdown(`Received ${signal}`)
      .then(() => {
        manifest.status = "cancelled";
        manifest.completedAt = new Date().toISOString();
        persistManifest();
      })
      .catch((error) => {
        manifest.status = "failed";
        manifest.error = error instanceof Error ? error.message : String(error);
        manifest.completedAt = new Date().toISOString();
        persistManifest();
      })
      .finally(() => process.exit(130));
  };

  process.on("SIGINT", signalHandler);
  process.on("SIGTERM", signalHandler);

  try {
    emitRunStatus("launching backend");
    launcher = spawnManagedProcess({
      label: "launcher",
      command: launcherCommand,
      cwd,
      logDir: paths.logDir,
      teeStdout: showLauncherOutput,
      teeStderr: showLauncherOutput,
    });
    manifest.processes.launcher = { pid: launcher.pid, command: launcher.command };
    persistManifest();

    emitRunStatus(`waiting for snapshot readiness at ${paths.snapshotUrl}`);
    await Promise.race([
      waitForRuntimeReady(paths.outputDir, paths.snapshotUrl, readinessTimeoutMs, options.readinessPollMs),
      waitForExit(launcher).then((code) => {
        throw new Error(`Launcher exited before readiness check completed (code ${code})`);
      }),
    ]);

    manifest.status = "ready";
    manifest.readyAt = new Date().toISOString();
    persistManifest();
    emitRunStatus("backend ready");

    if (options.monitor) {
      emitRunStatus("attaching OpenTUI monitor");
      clearRunStatus();
      const monitorCommand = buildMonitorCommand(options, cwd, paths.snapshotUrl);
      monitor = spawnManagedProcess({
        label: "monitor",
        command: monitorCommand,
        cwd,
        env: {
          ENTROPYHUNT_WATCH_PARENT_PID: String(process.pid),
          ENTROPYHUNT_EXIT_ON_SOURCE_LOSS_MS: "15000",
        },
        logDir: paths.logDir,
        teeStdout: false,
        teeStderr: false,
        stdioMode: "inherit",
      });
      manifest.processes.monitor = { pid: monitor.pid, command: monitor.command };
      manifest.paths.monitorStdout = monitor.stdoutPath;
      manifest.paths.monitorStderr = monitor.stderrPath;
      persistManifest();
    }

    manifest.status = "running";
    persistManifest();
    if (!interactiveMonitorMode) {
      emitRunStatus("runtime active");
    }

    const launcherCode = await waitForExit(launcher);
    manifest.exit = { ...manifest.exit, launcherCode };

    if (monitor) {
      if (options.monitorHoldOpen && launcherCode === 0) {
        const monitorCode = await waitForExit(monitor);
        manifest.exit = { ...manifest.exit, monitorCode };
      } else {
        await terminateManagedProcess(monitor, 500);
        const monitorCode = monitor.child.exitCode ?? 0;
        manifest.exit = { ...manifest.exit, monitorCode };
      }
    }

    manifest.status = launcherCode === 0 ? "completed" : "failed";
    manifest.completedAt = new Date().toISOString();
    persistManifest();
    printSessionSummary(launcherCode, manifest.exit.monitorCode);
    return launcherCode;
  } catch (error) {
    manifest.status = "failed";
    manifest.error = error instanceof Error ? error.message : String(error);
    manifest.completedAt = new Date().toISOString();
    persistManifest();
    await shutdown(manifest.error);
    printSessionSummary(1, monitor?.child.exitCode ?? undefined);
    return 1;
  } finally {
    process.off("SIGINT", signalHandler);
    process.off("SIGTERM", signalHandler);
  }
}

void main().then((code) => {
  process.exitCode = code;
});
