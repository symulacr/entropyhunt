import React from 'react'
import type { Drone } from '@/types/console'
import styles from '@/styles/console.module.css'

interface DroneRosterProps {
  drones: Drone[]
  grid: { certainty: number }[][]
  onKillDrone: (droneId: string) => void
}

function entropyValue(certainty: number): number {
  if (certainty <= 0 || certainty >= 1) return 0
  return -(certainty * Math.log2(certainty) + (1 - certainty) * Math.log2(1 - certainty))
}

function mapBackendStatus(rawStatus: string): string {
  return (
    {
      transiting: 'transit',
      claiming: 'transit',
      claim_won: 'searching',
      claim_lost: 'transit',
      stale: 'offline',
    } as Record<string, string>
  )[rawStatus] || rawStatus || 'idle'
}

const DroneRoster: React.FC<DroneRosterProps> = ({ drones, grid, onKillDrone }) => {
  return (
    <div className={styles.sideBlock} style={{ flex: '0 0 auto' }}>
      <div className={styles.sideHead}>
        Drone Roster
        <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--text-muted)' }}>
          Click row to kill
        </span>
      </div>
      <div>
        {drones.map((drone) => {
          const displayStatus = mapBackendStatus(drone.status)
          const chipClass =
            drone.stale
              ? styles.chipD
              : displayStatus === 'searching'
                ? styles.chipS
                : displayStatus === 'transit'
                  ? styles.chipT
                  : styles.chipI
          const chipText = drone.stale
            ? 'offline'
            : displayStatus === 'searching'
              ? 'searching'
              : displayStatus === 'transit'
                ? 'transit'
                : 'idle'
          const currentEntropy = entropyValue(grid[drone.y]?.[drone.x]?.certainty ?? 0.5).toFixed(2)
          const target = drone.tx == null || drone.ty == null ? '[--,--]' : `[${drone.tx},${drone.ty}]`
          const ownership =
            drone.tx == null || drone.ty == null ? 'unclaimed' : `claim [${drone.tx},${drone.ty}]`
          const battery = drone.battery != null ? `bat=${drone.battery}%` : ''
          const role = drone.role ? `role=${drone.role}` : ''
          const subzone = drone.subzone ? `zone=${drone.subzone}` : ''
          const extra = [battery, role, subzone].filter(Boolean).join(' \u00b7 ')

          return (
            <div
              key={drone.id}
              className={`${styles.droneRow} ${drone.stale ? styles.stale : ''}`}
              onClick={() => onKillDrone(drone.id)}
            >
              <div className={styles.drDot} style={{ background: drone.color }} />
              <span className={styles.drName}>{drone.id}</span>
              <span className={styles.drPos}>[{drone.x},{drone.y}]</span>
              <span className={styles.drTarget}>-&gt;{target}</span>
              <span className={styles.drH}>
                H={currentEntropy} &middot; cells={drone.cells} &middot; {ownership}
                {extra ? ` \u00b7 ${extra}` : ''}
              </span>
              <span className={`${styles.chip} ${chipClass}`}>{chipText}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default React.memo(DroneRoster)
