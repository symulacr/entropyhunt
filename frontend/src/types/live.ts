export interface GridCell {
  certainty: number;
  owner: number | null;
}

export interface Drone {
  id: string;
  status: string;
  alive: boolean;
  reachable: boolean;
  position: [number, number];
  x?: number;
  y?: number;
  target: [number, number] | null;
  tx?: number;
  ty?: number;
  searched_cells: number;
  cells?: number;
  battery: number | null;
  role: string;
  subzone: string;
  stale?: boolean;
}

export interface TelemetryEvent {
  type: string;
  t?: number;
  message?: string;
  msg?: string;
}

export interface MeshPeer {
  peer_id: string;
  stale: boolean;
  last_seen_ms?: number;
}

export interface Mesh {
  transport?: string;
  peers: MeshPeer[];
  messages?: number;
}

export interface ConsensusRound {
  round_id: number;
  cell: [number, number] | null;
  vote_count: number;
  status: string;
}

export interface Failure {
  drone_id: string;
  t: number;
  failure_type?: string;
  recovered: boolean;
}

export interface SystemMetricsData {
  tick_seconds?: number;
  tick_delay_seconds?: number | null;
  requested_drone_count?: number;
  target?: [number, number];
}

export interface Stats {
  coverage?: number;
  average_entropy?: number;
  auctions?: number;
  dropouts?: number;
  duration_elapsed?: number;
  consensus_rounds?: number;
  mesh_messages?: number;
  survivor_receipts?: number;
  survivor_found?: boolean;
  tick_seconds?: number;
}

export interface Config {
  target?: [number, number];
  grid?: number;
}

export interface Summary {
  drones: Drone[];
  coverage?: number;
  coverage_completed?: number;
  coverage_current?: number;
  average_entropy?: number;
  auctions?: number;
  dropouts?: number;
  duration_elapsed?: number;
  consensus_rounds?: number;
  mesh_messages?: number;
  survivor_receipts?: number;
  survivor_found?: boolean;
  tick_seconds?: number;
  target?: [number, number];
  consensus?: ConsensusRound[];
  failures?: Failure[];
}

export interface SnapshotPayload {
  grid: GridCell[][];
  summary: Summary;
  stats?: Stats;
  events?: TelemetryEvent[];
  mesh?: Mesh;
  system?: SystemMetricsData;
  config?: Config;
}
