export type RuntimeSession = {
  startedAt: string;
  swarmPid: number;
  monitorPid: number;
  basePort: number;
  servePort: number;
  proofsPath: string;
  outputDir: string;
  logs: { swarm: string; monitor: string };
};
