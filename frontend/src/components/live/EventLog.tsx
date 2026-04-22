import React from "react";
import type { TelemetryEvent } from "@/types/live";
import { mapEventType } from "@/lib/liveUtils";
import styles from "@/styles/live.module.css";

interface EventLogProps {
  events: TelemetryEvent[];
  elapsed: number;
}

const EventLog: React.FC<EventLogProps> = ({ events, elapsed }) => {
  if (!events || !events.length) {
    return (
      <div className={styles.muted} style={{ padding: "8px", fontSize: "0.75rem" }}>
        No events recorded
      </div>
    );
  }

  return (
    <div className={styles.eventLog}>
      {[...events].reverse().map((ev, idx) => {
        const type = mapEventType(ev.type);
        const t = ev.t ?? elapsed ?? 0;
        return (
          <div key={idx} className={styles.eventRow}>
            <span className={`${styles.eventBadge} ${styles[type]}`}>{type}</span>
            <span className={styles.eventTime}>{t}s</span>
            <span className={styles.eventMsg}>{ev.message || ev.msg || ev.type || "event"}</span>
          </div>
        );
      })}
    </div>
  );
};

export default EventLog;
