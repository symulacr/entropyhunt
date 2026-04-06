import { randomUUID } from "node:crypto";
import * as path from "node:path";

export type RuntimeOptions = {
  mode: "peer" | "ros2";
  preset: "demo" | "stress-peers" | "stress-grid";
  count: number;
  duration: number;
  grid: number;
  tickSeconds: number;
  tickDelaySeconds?: number;
  target: string;
  failDrone: string;
  failAt: number;
  transport: "local" | "foxmq";
  mqttHost: string;
  mqttBasePort: number;
  serveHost: string;
  basePort?: number;
  servePort?: number;
  pythonBin: string;
  launcherScript: string;
  monitorScript: string;
  monitorBinary?: string;
  monitor: boolean;
  readinessTimeoutMs: number;
  readinessPollMs: number;
  sessionRoot: string;
  sessionName: string;
  launcherOutputMode: "auto" | "show" | "quiet";
  monitorHoldOpen: boolean;
  rosRuntime: "host" | "docker";
  rosDistro: string;
  rosWorkspace: string;
  rosPackage: string;
  rosLaunchFile: string;
  rosSnapshotHost: string;
  rosSnapshotPort: number;
  rosSnapshotPortExplicit: boolean;
  rosSnapshotPath: string;
  rosAutoBuild: boolean;
  dockerImage: string;
};

const DEFAULTS: RuntimeOptions = {
  mode: "peer",
  preset: "demo",
  count: 5,
  duration: 180,
  grid: 10,
  tickSeconds: 1,
  tickDelaySeconds: undefined,
  target: "7,3",
  failDrone: "drone_2",
  failAt: 60,
  transport: "local",
  mqttHost: "127.0.0.1",
  mqttBasePort: 1883,
  serveHost: "127.0.0.1",
  pythonBin: "python3",
  launcherScript: "scripts/run_local_peers.py",
  monitorScript: "dashboard/tui_monitor_v2.ts",
  monitorBinary: undefined,
  monitor: true,
  readinessTimeoutMs: 20_000,
  readinessPollMs: 250,
  sessionRoot: path.join("runtime", "sessions"),
  sessionName: defaultSessionName(),
  launcherOutputMode: "auto",
  monitorHoldOpen: true,
  rosRuntime: "host",
  rosDistro: process.env.ROS_DISTRO || "humble",
  rosWorkspace: "ros2_ws",
  rosPackage: "entropy_hunt_ros2",
  rosLaunchFile: "demo.launch.py",
  rosSnapshotHost: "127.0.0.1",
  rosSnapshotPort: 0,
  rosSnapshotPortExplicit: false,
  rosSnapshotPath: "",
  rosAutoBuild: true,
  dockerImage: "entropyhunt-ros2:humble",
};

function defaultSessionName(): string {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  return `hunt-${stamp}-${randomUUID().slice(0, 8)}`;
}

function expectValue(argv: string[], index: number, flag: string): string {
  const value = argv[index + 1];
  if (!value) {
    throw new Error(`Missing value for ${flag}`);
  }
  return value;
}

export function formatRuntimeHelp(): string {
  return [
    "Entropy Hunt runtime",
    "",
    "Usage:",
    "  bun run hunt [-- <options>]",
    "  ./build/entropyhunt <options>",
    "",
    "Core modes:",
    "  --mode peer                        Run the current Python peer runtime (default)",
    "  --mode ros2 --ros-runtime host    Run the ROS 2 lane on a host ROS install",
    "  --mode ros2 --ros-runtime docker  Run the ROS 2 lane in Docker",
    "",
    "Common options:",
    "  --count <n>               Number of agents/peers",
    "  --duration <seconds>      Simulation duration",
    "  --grid <n>                Grid size",
    "  --target <x,y>            Survivor/goal coordinate",
    "  --fail <peer_id>          Peer to fail",
    "  --fail-at <seconds>       Failure time",
    "  --no-monitor              Launch backend only",
    "  --show-launcher           Show backend logs in the active terminal",
    "",
    "ROS options:",
    "  --ros-distro <name>       ROS distro name (default: humble)",
    "  --ros-workspace <path>    ROS workspace root (default: ros2_ws)",
    "  --ros-package <name>      ROS package to launch",
    "  --ros-launch-file <file>  Launch file name",
    "  --ros-snapshot-host <h>   Snapshot host (default: 127.0.0.1)",
    "  --ros-snapshot-port <p>   Snapshot port (default: auto free port)",
    "  --ros-snapshot-path <p>   Snapshot file path override",
    "  --no-ros-auto-build       Skip colcon build before launch",
    "",
    "Examples:",
    "  bun run hunt",
    "  bun run hunt -- --count 8 --duration 240",
    "  bun run hunt -- --mode ros2 --ros-runtime docker --count 2",
    "  ./build/entropyhunt --mode peer --count 2 --duration 10 --no-monitor",
  ].join("\n");
}

export function parseRuntimeArgs(argv: string[]): RuntimeOptions {
  const options: RuntimeOptions = { ...DEFAULTS };

  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (!flag) continue;

    switch (flag) {
      case "--mode": {
        const value = expectValue(argv, index, flag);
        if (value !== "peer" && value !== "ros2") {
          throw new Error(`Unsupported mode: ${value}`);
        }
        options.mode = value;
        index += 1;
        break;
      }
      case "--count":
        options.count = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--preset": {
        const value = expectValue(argv, index, flag) as RuntimeOptions["preset"];
        if (!["demo", "stress-peers", "stress-grid"].includes(value)) {
          throw new Error(`Unknown preset: ${value}`);
        }
        options.preset = value;
        if (value === "demo") {
          options.count = 5;
          options.duration = 180;
          options.grid = 10;
          options.target = "7,3";
          options.failDrone = "drone_2";
          options.failAt = 60;
        } else if (value === "stress-peers") {
          options.count = 8;
          options.duration = 240;
          options.grid = 10;
          options.target = "7,3";
          options.failDrone = "drone_2";
          options.failAt = 60;
        } else {
          options.count = 5;
          options.duration = 240;
          options.grid = 20;
          options.target = "15,10";
          options.failDrone = "drone_2";
          options.failAt = 60;
        }
        index += 1;
        break;
      }
      case "--duration":
        options.duration = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--grid":
        options.grid = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--tick-seconds":
        options.tickSeconds = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--tick-delay-seconds":
        options.tickDelaySeconds = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--target":
        options.target = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--fail":
        options.failDrone = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--fail-at":
        options.failAt = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--transport": {
        const value = expectValue(argv, index, flag);
        if (value !== "local" && value !== "foxmq") {
          throw new Error(`Unsupported transport: ${value}`);
        }
        options.transport = value;
        index += 1;
        break;
      }
      case "--mqtt-host":
        options.mqttHost = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--mqtt-base-port":
        options.mqttBasePort = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--serve-host":
        options.serveHost = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--base-port":
        options.basePort = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--serve-port":
        options.servePort = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--python-bin":
        options.pythonBin = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--launcher-script":
        options.launcherScript = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--monitor-script":
        options.monitorScript = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--monitor-binary":
        options.monitorBinary = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--session-root":
        options.sessionRoot = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--session-name":
        options.sessionName = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--readiness-timeout-ms":
        options.readinessTimeoutMs = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--readiness-poll-ms":
        options.readinessPollMs = Number(expectValue(argv, index, flag));
        index += 1;
        break;
      case "--monitor":
        options.monitor = true;
        break;
      case "--no-monitor":
        options.monitor = false;
        break;
      case "--launcher-output": {
        const value = expectValue(argv, index, flag);
        if (value !== "auto" && value !== "show" && value !== "quiet") {
          throw new Error(`Unsupported launcher output mode: ${value}`);
        }
        options.launcherOutputMode = value;
        index += 1;
        break;
      }
      case "--show-launcher":
        options.launcherOutputMode = "show";
        break;
      case "--quiet-launcher":
        options.launcherOutputMode = "quiet";
        break;
      case "--ros-runtime": {
        const value = expectValue(argv, index, flag);
        if (value !== "host" && value !== "docker") {
          throw new Error(`Unsupported ros runtime: ${value}`);
        }
        options.rosRuntime = value;
        index += 1;
        break;
      }
      case "--ros-distro":
        options.rosDistro = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--ros-workspace":
        options.rosWorkspace = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--ros-package":
        options.rosPackage = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--ros-launch-file":
        options.rosLaunchFile = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--ros-snapshot-host":
        options.rosSnapshotHost = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--ros-snapshot-port":
        options.rosSnapshotPort = Number(expectValue(argv, index, flag));
        options.rosSnapshotPortExplicit = true;
        index += 1;
        break;
      case "--ros-snapshot-path":
        options.rosSnapshotPath = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--ros-auto-build":
        options.rosAutoBuild = true;
        break;
      case "--no-ros-auto-build":
        options.rosAutoBuild = false;
        break;
      case "--docker-image":
        options.dockerImage = expectValue(argv, index, flag);
        index += 1;
        break;
      case "--hold-monitor-open":
        options.monitorHoldOpen = true;
        break;
      case "--close-monitor-on-complete":
        options.monitorHoldOpen = false;
        break;
      default:
        throw new Error(`Unknown flag: ${flag}`);
    }
  }

  if (!Number.isInteger(options.count) || options.count <= 0) {
    throw new Error(`--count must be a positive integer; received ${options.count}`);
  }
  if (!Number.isInteger(options.duration) || options.duration <= 0) {
    throw new Error(`--duration must be a positive integer; received ${options.duration}`);
  }
  if (!Number.isInteger(options.grid) || options.grid <= 0) {
    throw new Error(`--grid must be a positive integer; received ${options.grid}`);
  }
  if (!Number.isInteger(options.failAt) || options.failAt < 0) {
    throw new Error(`--fail-at must be a non-negative integer; received ${options.failAt}`);
  }
  if (options.tickDelaySeconds != null && (!Number.isFinite(options.tickDelaySeconds) || options.tickDelaySeconds < 0)) {
    throw new Error(`--tick-delay-seconds must be a non-negative number; received ${options.tickDelaySeconds}`);
  }
  if (!Number.isInteger(options.rosSnapshotPort) || options.rosSnapshotPort < 0) {
    throw new Error(`--ros-snapshot-port must be a non-negative integer; received ${options.rosSnapshotPort}`);
  }

  return options;
}
