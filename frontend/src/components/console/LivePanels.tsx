import React from 'react'
import type { SnapshotSummary, SnapshotSystem } from '@/types/console'
import styles from '@/styles/console.module.css'

interface LivePanelsProps {
  summary: SnapshotSummary | null
  system: SnapshotSystem | null
  visible: boolean
}

const LivePanels: React.FC<LivePanelsProps> = ({ summary, system, visible }) => {
  if (!visible) return null

  const meshPeers = summary?.mesh_peers || []
  const consensus = summary?.consensus || []
  const failures = summary?.failures || []
  const sys = system || {}
  const tickSec = sys.tick_seconds || summary?.tick_seconds || 1
  const tickDelay = sys.tick_delay_seconds != null ? sys.tick_delay_seconds : (summary?.tick_delay_seconds || 0.1)
  const reqDrones = sys.requested_drone_count || summary?.requested_drone_count || 5
  const target = sys.target || summary?.target || [7, 3]

  return (
    <>
      <div className={styles.sideBlock} style={{ flex: '0 0 auto' }}>
        <div className={styles.sideHead}>Mesh Peers</div>
        <div className={styles.sideBody}>
          {!meshPeers.length ? (
            <div className={styles.emptyState}>No mesh peers</div>
          ) : (
            meshPeers.map((peer, i) => {
              const stale = peer.stale
              const dotColor = stale ? 'var(--error)' : 'var(--ok)'
              const lastSeen = peer.last_seen_ms ? Math.round(peer.last_seen_ms / 1000) + 's' : '--'
              return (
                <div key={`${peer.peer_id ?? i}-${i}`} className={styles.livePeerRow}>
                  <div className={styles.livePeerDot} style={{ background: dotColor }} />
                  <span className={styles.livePeerId}>{peer.peer_id || 'unknown'}</span>
                  <span className={styles.livePeerMeta}>
                    last {lastSeen}{stale ? ' \u00b7 STALE' : ''}
                  </span>
                </div>
              )
            })
          )}
        </div>
      </div>

      <div className={styles.sideBlock} style={{ flex: '0 0 auto' }}>
        <div className={styles.sideHead}>Consensus Rounds</div>
        <div className={styles.sideBody}>
          {!consensus.length ? (
            <div className={styles.emptyState}>No consensus rounds</div>
          ) : (
            consensus.slice().reverse().map((round, i) => {
              const cell = round.cell ? `[${round.cell[0]},${round.cell[1]}]` : '--'
              return (
                <div key={`${round.round_id ?? i}-${i}`} className={styles.liveConsensusRow}>
                  <span style={{ color: 'var(--text)', fontWeight: 600 }}>#{round.round_id || 0}</span>
                  <span style={{ color: 'var(--accent)' }}>{cell}</span>
                  <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>{round.vote_count || 0} votes</span>
                </div>
              )
            })
          )}
        </div>
      </div>

      <div className={styles.sideBlock} style={{ flex: '0 0 auto' }}>
        <div className={styles.sideHead}>Failures</div>
        <div className={styles.sideBody}>
          {!failures.length ? (
            <div className={styles.emptyState}>No failures</div>
          ) : (
            failures.slice().reverse().map((f, i) => {
              const badge = f.recovered
                ? <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'var(--ok-soft)', color: 'var(--ok)', fontWeight: 600 }}>recovered</span>
                : <span style={{ fontSize: 9, padding: '2px 6px', borderRadius: 4, background: 'var(--error-soft)', color: 'var(--error)', fontWeight: 600 }}>{f.failure_type || 'failure'}</span>
              return (
                <div key={`${f.drone_id ?? i}-${i}`} className={styles.liveFailureRow}>
                  {badge}
                  <span style={{ color: 'var(--text)', fontWeight: 600 }}>{f.drone_id || 'unknown'}</span>
                  <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>t={f.t || 0}s</span>
                </div>
              )
            })
          )}
        </div>
      </div>

      <div className={styles.sideBlock} style={{ flex: '0 0 auto' }}>
        <div className={styles.sideHead}>System</div>
        <div className={styles.sideBody}>
          <div className={styles.liveSystemRow}>
            <span className={styles.liveSystemK}>Tick Seconds</span>
            <span className={styles.liveSystemV}>{tickSec}</span>
          </div>
          <div className={styles.liveSystemRow}>
            <span className={styles.liveSystemK}>Tick Delay</span>
            <span className={styles.liveSystemV}>{tickDelay}s</span>
          </div>
          <div className={styles.liveSystemRow}>
            <span className={styles.liveSystemK}>Requested Drones</span>
            <span className={styles.liveSystemV}>{reqDrones}</span>
          </div>
          <div className={styles.liveSystemRow}>
            <span className={styles.liveSystemK}>Target</span>
            <span className={styles.liveSystemV}>[{target.join(',')}]</span>
          </div>
        </div>
      </div>
    </>
  )
}

export default React.memo(LivePanels)
