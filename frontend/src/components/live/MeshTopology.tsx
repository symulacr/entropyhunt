import React from "react";
import type { Mesh } from "@/types/live";
import styles from "@/styles/live.module.css";

interface MeshTopologyProps {
  mesh: Mesh | undefined;
}

const MeshTopology: React.FC<MeshTopologyProps> = ({ mesh }) => {
  if (!mesh || !mesh.peers || !mesh.peers.length) {
    return (
      <div className={styles.stateMsgWaiting}>
        <div className={styles.stateMsgContent}>No mesh peers connected</div>
      </div>
    );
  }

  return (
    <div>
      {mesh.peers.map((peer) => {
        const stale = peer.stale;
        const dotColor = stale ? "var(--error)" : "var(--ok)";
        const lastSeen = peer.last_seen_ms
          ? `${Math.round(peer.last_seen_ms / 1000)}s`
          : "--";
        return (
          <div key={peer.peer_id} className={styles.meshPeerRow}>
            <div className={styles.meshPeerDot} style={{ background: dotColor }} />
            <span className={styles.meshPeerId}>{peer.peer_id || "unknown"}</span>
            <span className={styles.meshPeerMeta}>
              last {lastSeen}
              {stale ? " &middot; STALE" : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
};

export default MeshTopology;
