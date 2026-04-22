import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import { useSSE } from "@/hooks/useSSE";
import { coverage, averageEntropy } from "@/lib/liveUtils";
import StatusBar from "@/components/live/StatusBar";
import KPIBar from "@/components/live/KPIBar";
import GridCanvas from "@/components/live/GridCanvas";
import DroneCards from "@/components/live/DroneCards";
import EventLog from "@/components/live/EventLog";
import MeshTopology from "@/components/live/MeshTopology";
import ConsensusPanel from "@/components/live/ConsensusPanel";
import FailureTimeline from "@/components/live/FailureTimeline";
import SystemMetrics from "@/components/live/SystemMetrics";
import styles from "@/styles/live.module.css";
import pageStyles from "./LivePage.module.css";

export const LivePage: React.FC = () => {
  const { payload, connectionState, connectionText, lastUpdate } = useSSE("/stream");

  const {
    grid,
    drones,
    target,
    elapsed,
    survivorFound,
    events,
    mesh,
    consensus,
    failures,
    system,
    gridMeta,
    droneCount,
    eventCount,
    meshMeta,
    consensusMeta,
    failureMeta,
    systemMeta,
    kpis,
  } = useMemo(() => {
    if (!payload) {
      return {
        grid: [] as import("@/types/live").GridCell[][],
        drones: [] as import("@/types/live").Drone[],
        target: [7, 3] as [number, number],
        elapsed: 0,
        survivorFound: false,
        events: [] as import("@/types/live").TelemetryEvent[],
        mesh: undefined as import("@/types/live").Mesh | undefined,
        consensus: [] as import("@/types/live").ConsensusRound[],
        failures: [] as import("@/types/live").Failure[],
        system: undefined as import("@/types/live").SystemMetricsData | undefined,
        gridMeta: "Waiting for snapshot",
        droneCount: "--",
        eventCount: "--",
        meshMeta: "--",
        consensusMeta: "--",
        failureMeta: "--",
        systemMeta: "--",
        kpis: Array.from({ length: 10 }, (_, i) => ({
          label: [
            "Coverage",
            "Avg Entropy",
            "Auctions",
            "Dropouts",
            "Elapsed",
            "Drones Online",
            "Consensus",
            "Mesh Msgs",
            "Survivor Rcpts",
            "Tick Rate",
          ][i],
          value: "--",
          variant: "default" as const,
        })),
      };
    }

    const gridData = payload.grid || [];
    const summary = payload.summary || payload || {};
    const stats = payload.stats || summary || {};
    const meshData = payload.mesh || { peers: [] };
    const systemData = payload.system;
    const dronesData = Array.isArray(summary.drones) ? summary.drones : [];
    const rawEvents = Array.isArray(payload.events) ? payload.events : [];
    const targetValue =
      payload.config?.target || summary.target || systemData?.target || [7, 3];
    const elapsedValue = Number(
      stats.duration_elapsed ?? summary.duration_elapsed ?? 0
    );

    const covValue =
      stats.coverage != null
        ? `${Math.round(stats.coverage * 100)}%`
        : `${coverage(gridData)}%`;
    const entValue =
      stats.average_entropy != null
        ? Number(stats.average_entropy).toFixed(2)
        : averageEntropy(gridData);
    const aucValue = String(stats.auctions ?? summary.auctions ?? 0);
    const dropValue = String(stats.dropouts ?? summary.dropouts ?? 0);
    const tValue = `${elapsedValue}s`;
    const liveCount = dronesData.filter(
      (d) => d.alive !== false && d.reachable !== false
    ).length;
    const liveValue = `${liveCount}/${dronesData.length}`;
    const conValue = String(stats.consensus_rounds ?? summary.consensus_rounds ?? 0);
    const msgValue = String(stats.mesh_messages ?? summary.mesh_messages ?? 0);
    const surValue = String(stats.survivor_receipts ?? summary.survivor_receipts ?? 0);
    const tickValue = `${systemData?.tick_seconds ?? summary.tick_seconds ?? 1}/s`;

    const size = gridData.length || 0;

    return {
      grid: gridData,
      drones: dronesData,
      target: targetValue as [number, number],
      elapsed: elapsedValue,
      survivorFound: Boolean(stats.survivor_found ?? summary.survivor_found),
      events: rawEvents,
      mesh: meshData,
      consensus: summary.consensus || [],
      failures: summary.failures || [],
      system: systemData,
      gridMeta: size ? `${size}x${size} grid` : "No grid",
      droneCount: `${dronesData.length} total`,
      eventCount: `${rawEvents.length} events`,
      meshMeta:
        meshData && meshData.peers.length
          ? `${meshData.transport || "local"} \u00b7 ${meshData.peers.length} peers \u00b7 ${meshData.messages || 0} msgs`
          : meshData.transport || "local",
      consensusMeta: `${summary.consensus?.length || 0} rounds`,
      failureMeta: `${summary.failures?.length || 0} events`,
      systemMeta: "peer runtime",
      kpis: [
        { label: "Coverage", value: covValue, variant: "ok" as const },
        { label: "Avg Entropy", value: entValue, variant: "accent" as const },
        { label: "Auctions", value: aucValue, variant: "default" as const },
        { label: "Dropouts", value: dropValue, variant: "warn" as const },
        { label: "Elapsed", value: tValue, variant: "default" as const },
        { label: "Drones Online", value: liveValue, variant: "ok" as const },
        { label: "Consensus", value: conValue, variant: "accent" as const },
        { label: "Mesh Msgs", value: msgValue, variant: "default" as const },
        { label: "Survivor Rcpts", value: surValue, variant: "ok" as const },
        { label: "Tick Rate", value: tickValue, variant: "default" as const },
      ],
    };
  }, [payload]);

  return (
    <div className={styles.livePage}>
      <div style={{ padding: "16px 24px", borderBottom: "1px solid var(--live-border)" }}>
        <Link to="/" className={pageStyles.backLink}>Back to Mission Control</Link>
      </div>
      <StatusBar
        connectionState={connectionState}
        connectionText={connectionText}
        lastUpdate={lastUpdate}
      />
      <KPIBar kpis={kpis} />

      <div className={styles.dashboard}>
        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <span>Grid Visualization</span>
            <span className={styles.muted}>{gridMeta}</span>
          </div>
          <div className={styles.panelBody}>
            {grid.length > 0 ? (
              <GridCanvas
                grid={grid}
                drones={drones}
                target={target}
                survivorFound={survivorFound}
              />
            ) : (
              <div className={styles.stateMsgWaiting}>
                <div className={styles.stateMsgContent}>Waiting for grid data</div>
              </div>
            )}
          </div>
        </div>

        <div className={styles.sidePanelStack}>
          <div className={styles.panel}>
            <div className={styles.panelHead}>
              <span>Drone Status</span>
              <span className={styles.muted}>{droneCount}</span>
            </div>
            <div className={styles.panelBody} style={{ padding: "12px" }}>
              <DroneCards drones={drones} />
            </div>
          </div>
          <div className={styles.panel}>
            <div className={styles.panelHead}>
              <span>Event Log</span>
              <span className={styles.muted}>{eventCount}</span>
            </div>
            <div className={styles.panelBody} style={{ padding: "12px" }}>
              <EventLog events={events} elapsed={elapsed} />
            </div>
          </div>
        </div>
      </div>

      <div className={styles.detailGrid}>
        <div className={styles.detailPanel}>
          <div className={styles.panelHead}>
            <span>Mesh Topology</span>
            <span className={styles.muted}>{meshMeta}</span>
          </div>
          <div className={styles.panelBody} style={{ padding: "12px" }}>
            <MeshTopology mesh={mesh} />
          </div>
        </div>
        <div className={styles.detailPanel}>
          <div className={styles.panelHead}>
            <span>Consensus Rounds</span>
            <span className={styles.muted}>{consensusMeta}</span>
          </div>
          <div className={styles.panelBody} style={{ padding: "12px" }}>
            <ConsensusPanel consensus={consensus} />
          </div>
        </div>
        <div className={styles.detailPanel}>
          <div className={styles.panelHead}>
            <span>Failure Timeline</span>
            <span className={styles.muted}>{failureMeta}</span>
          </div>
          <div className={styles.panelBody} style={{ padding: "12px" }}>
            <FailureTimeline failures={failures} />
          </div>
        </div>
        <div className={styles.detailPanel}>
          <div className={styles.panelHead}>
            <span>System Metrics</span>
            <span className={styles.muted}>{systemMeta}</span>
          </div>
          <div className={styles.panelBody} style={{ padding: "12px" }}>
            <SystemMetrics system={system} />
          </div>
        </div>
      </div>
    </div>
  );
};
