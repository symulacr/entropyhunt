export type SourceMode = 'synthetic' | 'replay' | 'live'

export interface Cell {
  x: number
  y: number
  certainty: number
  owner: number
  ownerId: string | null
}

export interface Drone {
  id: string
  color: string
  x: number
  y: number
  tx: number | null
  ty: number | null
  stale: boolean
  status: string
  cells: number
  battery?: number | null
  role?: string | null
  subzone?: string | null
}

export interface LogEvent {
  type: 'bft' | 'ok' | 'err' | 'warn' | 'info'
  msg: string
  t: number
}

export interface AutoDemoState {
  enabled: boolean
  packetLoss: boolean
  contention: boolean
  dropout: boolean
  survivor: boolean
}

export interface ToastState {
  type: 'ok' | 'err' | 'info' | 'warn'
  message: string
  visible: boolean
}

export interface SyntheticBaseline {
  grid: Cell[][]
  drones: Drone[]
  elapsed: number
  bftRounds: number
  auctions: number
  dropouts: number
  found: boolean
  missionComplete: boolean
  events: LogEvent[]
  packetDrop: boolean
}

export interface SnapshotCell {
  x?: number
  y?: number
  certainty?: number
  owner?: number | string
  ownerId?: string | null
}

export interface SnapshotDrone {
  id?: string
  position?: [number, number]
  target?: [number, number] | null
  alive?: boolean
  reachable?: boolean
  status?: string
  searched_cells?: number
  battery?: number | null
  role?: string | null
  subzone?: string | null
  claimed_cell?: [number, number] | null
}

export interface SnapshotConsensusRound {
  round_id?: number
  cell?: [number, number]
  vote_count?: number
}

export interface SnapshotFailure {
  drone_id?: string
  failure_type?: string
  recovered?: boolean
  t?: number
}

export interface SnapshotMeshPeer {
  peer_id?: string
  stale?: boolean
  last_seen_ms?: number
}

export interface SnapshotSystem {
  tick_seconds?: number
  tick_delay_seconds?: number
  requested_drone_count?: number
  target?: [number, number]
}

export interface SnapshotSummary {
  drones?: SnapshotDrone[]
  consensus_rounds?: number
  mesh_messages?: number
  survivor_receipts?: number
  duration_elapsed?: number
  bft_rounds?: number
  auctions?: number
  dropouts?: number
  survivor_found?: boolean
  mesh_peers?: SnapshotMeshPeer[]
  consensus?: SnapshotConsensusRound[]
  failures?: SnapshotFailure[]
  tick_seconds?: number
  tick_delay_seconds?: number
  requested_drone_count?: number
  target?: [number, number]
}

export interface SnapshotPayload {
  grid?: SnapshotCell[][]
  summary?: SnapshotSummary
  stats?: SnapshotSummary
  events?: Array<{
    type?: string
    message?: string
    t?: number
  }>
  config?: {
    target?: [number, number]
  }
  mesh?: {
    peers?: SnapshotMeshPeer[]
  }
  system?: SnapshotSystem
}
