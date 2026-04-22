import React from "react";
import type { Drone } from "@/types/live";
import { COLORS, mapBackendStatus } from "@/lib/liveUtils";
import styles from "@/styles/live.module.css";

interface DroneCardsProps {
  drones: Drone[];
}

const DroneCards: React.FC<DroneCardsProps> = ({ drones }) => {
  if (!drones || !drones.length) {
    return (
      <div className={styles.stateMsgWaiting}>
        <div className={styles.stateMsgContent}>Waiting for drone data</div>
      </div>
    );
  }

  return (
    <div className={styles.droneCards}>
      {drones.map((drone, index) => {
        const color = COLORS[index % COLORS.length] || "#888";
        const status = mapBackendStatus(drone.status);
        const stale = drone.alive === false || drone.reachable === false;
        const pos = drone.position
          ? `[${drone.position[0]},${drone.position[1]}]`
          : "[--,--]";
        const cells = drone.searched_cells ?? drone.cells ?? 0;
        const battery = drone.battery != null ? `${drone.battery}%` : "--";
        const role = drone.role || "--";
        const subzone = drone.subzone || "--";
        const chipClass = stale
          ? "offline"
          : status === "searching"
            ? "searching"
            : status === "transit"
              ? "transit"
              : "idle";
        const chipText = stale ? "OFFLINE" : status.toUpperCase();

        return (
          <div
            key={drone.id || `drone_${index}`}
            className={`${styles.droneCard} ${stale ? styles.offline : ""}`}
          >
            <div className={styles.droneDot} style={{ background: color }} />
            <div className={styles.droneInfo}>
              <div className={styles.droneId}>{drone.id || `drone_${index + 1}`}</div>
              <div className={styles.droneMeta}>
                {pos} &middot; cells={cells} &middot; bat={battery} &middot; role={role}{" "}
                &middot; zone={subzone}
              </div>
            </div>
            <span className={`${styles.droneChip} ${styles[chipClass]}`}>{chipText}</span>
          </div>
        );
      })}
    </div>
  );
};

export default DroneCards;
