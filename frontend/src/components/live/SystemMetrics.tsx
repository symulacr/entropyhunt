import React from "react";
import type { SystemMetricsData } from "@/types/live";
import styles from "@/styles/live.module.css";

interface SystemMetricsProps {
  system: SystemMetricsData | undefined;
}

const SystemMetrics: React.FC<SystemMetricsProps> = ({ system }) => {
  if (!system) {
    return (
      <div className={styles.stateMsgWaiting}>
        <div className={styles.stateMsgContent}>No system data</div>
      </div>
    );
  }

  return (
    <div className={styles.sysMetrics}>
      <div className={styles.sysMetric}>
        <div className={styles.sysMetricK}>Tick Seconds</div>
        <div className={styles.sysMetricV}>{system.tick_seconds ?? "--"}</div>
      </div>
      <div className={styles.sysMetric}>
        <div className={styles.sysMetricK}>Tick Delay</div>
        <div className={styles.sysMetricV}>
          {system.tick_delay_seconds != null ? `${system.tick_delay_seconds}s` : "--"}
        </div>
      </div>
      <div className={styles.sysMetric}>
        <div className={styles.sysMetricK}>Requested Drones</div>
        <div className={styles.sysMetricV}>{system.requested_drone_count ?? "--"}</div>
      </div>
      <div className={styles.sysMetric}>
        <div className={styles.sysMetricK}>Target</div>
        <div className={styles.sysMetricV}>
          [{system.target ? system.target.join(",") : "--"}]
        </div>
      </div>
    </div>
  );
};

export default SystemMetrics;
