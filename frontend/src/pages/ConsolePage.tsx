import React, { useMemo } from 'react'
import { useConsoleEngine } from '@/hooks/useConsoleEngine'
import ConsoleHeader from '@/components/console/ConsoleHeader'
import ConsoleKVBar from '@/components/console/ConsoleKVBar'
import GridCanvas from '@/components/console/GridCanvas'
import DroneRoster from '@/components/console/DroneRoster'
import EventLog from '@/components/console/EventLog'
import LivePanels from '@/components/console/LivePanels'
import Controls from '@/components/console/Controls'
import ConsoleFooter from '@/components/console/ConsoleFooter'
import Toast from '@/components/console/Toast'
import styles from '@/styles/console.module.css'

export const ConsolePage: React.FC = () => {
  const engine = useConsoleEngine()

  const liveSummary = useMemo(() => {
    if (engine.sourceMode !== 'live') return null
    return {
      mesh_peers: [] as { peer_id?: string; stale?: boolean; last_seen_ms?: number }[],
      consensus: [] as { round_id?: number; cell?: [number, number]; vote_count?: number }[],
      failures: [] as { drone_id?: string; failure_type?: string; recovered?: boolean; t?: number }[],
      consensus_rounds: engine.bftRounds,
      mesh_messages: 0,
      survivor_receipts: 0,
      tick_seconds: 1,
      tick_delay_seconds: 0.1,
      requested_drone_count: 5,
      target: [engine.target.x, engine.target.y] as [number, number],
    }
  }, [engine.sourceMode, engine.bftRounds, engine.target])

  const liveSystem = useMemo(() => {
    if (engine.sourceMode !== 'live') return null
    return {
      tick_seconds: 1,
      tick_delay_seconds: 0.1,
      requested_drone_count: 5,
      target: [engine.target.x, engine.target.y] as [number, number],
    }
  }, [engine.sourceMode, engine.target])

  return (
    <div className={styles.root}>
      <a href="#main-panel" className={styles.skipLink}>
        Skip to console
      </a>

      <ConsoleHeader
        sourceMode={engine.sourceMode}
        liveUrl={engine.liveUrl}
        onLiveUrlChange={engine.setLiveUrl}
        onConnectLive={engine.connectLive}
        onDisconnectLive={engine.disconnectLive}
        onClearReplay={engine.clearReplay}
        onDropPackets={engine.dropPackets}
        onToggleAutoDemo={engine.toggleAutoDemo}
        onKillRandom={engine.killRandom}
        onReviveAll={engine.reviveAll}
        onFileLoad={engine.handleFileLoad}
        isLiveConnected={engine.sourceMode === 'live'}
        isReplayLoaded={engine.sourceMode === 'replay'}
        packetDropActive={engine.packetDrop}
        autoDemoEnabled={engine.autoDemo.enabled}
      />

      <div className={styles.missionBanner}>
        Autonomous SAR swarm coordinating in degraded conditions
      </div>

      <ConsoleKVBar
        coverage={engine.coverage()}
        avgEntropy={engine.averageEntropy()}
        auctions={engine.auctions}
        dropouts={engine.dropouts}
        elapsed={engine.elapsed}
        bftRounds={engine.bftRounds}
        meshMessages={engine.sourceMode === 'live' ? 0 : 0}
        survivorReceipts={engine.found ? 1 : 0}
      />

      <div className={styles.body} id="main-panel">
        <GridCanvas
          grid={engine.grid}
          drones={engine.drones}
          target={engine.target}
          found={engine.found}
          onKillDrone={engine.killDrone}
          loading={engine.loading}
        />

        <div className={styles.side}>
          <DroneRoster
            drones={engine.drones}
            grid={engine.grid}
            onKillDrone={engine.killDrone}
          />

          <Controls
            speed={engine.speed}
            onSpeedChange={engine.setSpeed}
            disabled={engine.sourceMode !== 'synthetic'}
          />

          <EventLog events={engine.events} />

          <LivePanels
            summary={liveSummary}
            system={liveSystem}
            visible={engine.sourceMode === 'live'}
          />
        </div>
      </div>

      <ConsoleFooter message={engine.footerMsg} />
      <Toast toast={engine.toast} />
    </div>
  )
}

export default ConsolePage
