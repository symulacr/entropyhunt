export const COLORS = ["#378ADD", "#1D9E75", "#BA7517", "#D85A30", "#D4537E"];

export function entropy(certainty: number): number {
  if (certainty <= 0 || certainty >= 1) return 0;
  return -(certainty * Math.log2(certainty) + (1 - certainty) * Math.log2(1 - certainty));
}

export function mapBackendStatus(raw: string): string {
  return (
    {
      transiting: "transit",
      claiming: "transit",
      claim_won: "searching",
      claim_lost: "transit",
      stale: "offline",
    } as Record<string, string>
  )[raw] || raw || "idle";
}

export function mapEventType(type: string): string {
  return (
    {
      auction: "bft",
      bft: "bft",
      failure: "err",
      stale: "err",
      heartbeat_timeout: "err",
      zone_release: "warn",
      zone_priority_reclaim: "ok",
      survivor: "ok",
      survivor_found: "ok",
      survivor_ack: "ok",
      zone_complete: "ok",
      claim: "info",
      mesh: "info",
      map: "info",
    } as Record<string, string>
  )[type] || "info";
}

export interface GridCell {
  certainty?: number
}

export function coverage(grid: GridCell[][] | undefined): number {
  if (!grid || !grid.length) return 0;
  let searched = 0;
  const complete = 0.92;
  for (const row of grid) {
    for (const cell of row) {
      if ((cell.certainty ?? 0) >= complete) searched += 1;
    }
  }
  return Math.round((searched / (grid.length * grid[0].length)) * 100);
}

export function averageEntropy(grid: GridCell[][] | undefined): string {
  if (!grid || !grid.length) return "0.00";
  let total = 0;
  for (const row of grid) {
    for (const cell of row) {
      total += entropy(cell.certainty ?? 0.5);
    }
  }
  return (total / (grid.length * grid[0].length)).toFixed(2);
}

export type ConnectionState = "connecting" | "live" | "reconnecting" | "error";
