import React from 'react'
import styles from '@/styles/console.module.css'

interface ConsoleHeaderProps {
  sourceMode: string
  liveUrl: string
  onLiveUrlChange: (value: string) => void
  onConnectLive: () => void
  onDisconnectLive: () => void
  onClearReplay: () => void
  onDropPackets: () => void
  onToggleAutoDemo: () => void
  onKillRandom: () => void
  onReviveAll: () => void
  onFileLoad: (file: File) => void
  isLiveConnected: boolean
  isReplayLoaded: boolean
  packetDropActive: boolean
  autoDemoEnabled: boolean
}

const ConsoleHeader: React.FC<ConsoleHeaderProps> = ({
  sourceMode,
  liveUrl,
  onLiveUrlChange,
  onConnectLive,
  onDisconnectLive,
  onClearReplay,
  onDropPackets,
  onToggleAutoDemo,
  onKillRandom,
  onReviveAll,
  onFileLoad,
  isLiveConnected,
  isReplayLoaded,
  packetDropActive,
  autoDemoEnabled,
}) => {
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onFileLoad(file)
    e.target.value = ''
  }

  return (
    <header className={styles.header}>
      <span className={styles.headerTitle}>Entropy Hunt</span>
      <span className={styles.headerTag}>Track 2 &middot; Search &amp; Rescue</span>
      <span
        className={`${styles.headerMode} ${sourceMode !== 'synthetic' ? styles.replay : ''}`}
        aria-live="polite"
        aria-atomic="true"
      >
        {sourceMode === 'replay'
          ? 'Replay Snapshot (Read-Only)'
          : sourceMode === 'live'
            ? 'Live Snapshot (Read-Only)'
            : 'Demo-Only Synthetic'}
      </span>
      <span className={styles.spacer} />
      <div className={styles.headerGroup}>
        <span className={styles.headerGroupLabel}>Replay &middot; Read-Only</span>
        <label className={`${styles.btn} ${styles.fileBtn}`}>
          Load Replay JSON
          <input type="file" accept="application/json" onChange={handleFileChange} />
        </label>
        <button className={styles.btn} disabled={!isReplayLoaded} onClick={onClearReplay}>
          Clear Replay
        </button>
      </div>
      <div className={styles.headerGroup}>
        <span className={styles.headerGroupLabel}>Live Helper &middot; Read-Only</span>
        <input
          className={styles.liveInput}
          value={liveUrl}
          onChange={(e) => onLiveUrlChange(e.target.value)}
        />
        <button className={styles.btn} disabled={isLiveConnected} onClick={onConnectLive}>
          Connect Live Snapshot
        </button>
        <button className={styles.btn} disabled={!isLiveConnected} onClick={onDisconnectLive}>
          Stop Live
        </button>
      </div>
      <div className={styles.headerGroup}>
        <span className={styles.headerGroupLabel}>Synthetic Demo Controls</span>
        <button
          className={`${styles.btn} ${styles.warn} ${packetDropActive ? styles.active : ''}`}
          disabled={sourceMode !== 'synthetic'}
          onClick={onDropPackets}
        >
          {packetDropActive ? 'Drop Packets On' : 'Drop Packets 20%'}
        </button>
        <button
          className={`${styles.btn} ${autoDemoEnabled ? styles.active : ''}`}
          disabled={sourceMode !== 'synthetic'}
          onClick={onToggleAutoDemo}
        >
          {autoDemoEnabled ? 'Auto Demo On' : 'Auto Demo Off'}
        </button>
        <button
          className={`${styles.btn} ${styles.danger}`}
          disabled={sourceMode !== 'synthetic'}
          onClick={onKillRandom}
        >
          Kill Drone
        </button>
        <button className={styles.btn} disabled={sourceMode !== 'synthetic'} onClick={onReviveAll}>
          Revive All
        </button>
      </div>
    </header>
  )
}

export default React.memo(ConsoleHeader)
