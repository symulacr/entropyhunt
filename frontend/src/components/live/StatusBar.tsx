import React from "react";
import type { ConnectionState } from "@/lib/liveUtils";
import styles from "@/styles/live.module.css";

interface StatusBarProps {
  connectionState: ConnectionState;
  connectionText: string;
  lastUpdate: string | null;
}

const StatusBar: React.FC<StatusBarProps> = ({ connectionState, connectionText, lastUpdate }) => {
  return (
    <header className={styles.topBar}>
      <div className={styles.brand}>
        <h1>Entropy Hunt</h1>
        <span className={styles.tagline}>Real-time search-and-rescue swarm coordination</span>
      </div>
      <div className={styles.statusGroup}>
        <div className={styles.statusPill}>
          <span className={`${styles.dot} ${styles[connectionState]}`} />
          <span>{connectionText}</span>
        </div>
        {lastUpdate && (
          <span className={styles.timestamp}>
            Last update: {lastUpdate}
          </span>
        )}
      </div>
    </header>
  );
};

export default StatusBar;
