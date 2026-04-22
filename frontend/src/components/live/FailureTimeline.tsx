import React from "react";
import type { Failure } from "@/types/live";
import styles from "@/styles/live.module.css";

interface FailureTimelineProps {
  failures: Failure[];
}

const FailureTimeline: React.FC<FailureTimelineProps> = ({ failures }) => {
  if (!failures || !failures.length) {
    return (
      <div className={styles.stateMsgWaiting}>
        <div className={styles.stateMsgContent}>No failures recorded</div>
      </div>
    );
  }

  return (
    <div>
      {[...failures].reverse().map((f, idx) => {
        const typeClass = f.recovered
          ? "recovered"
          : f.failure_type || "failure";
        return (
          <div key={idx} className={styles.failureRow}>
            <span className={`${styles.failureType} ${styles[typeClass]}`}>
              {f.recovered ? "recovered" : f.failure_type || "failure"}
            </span>
            <span className={styles.failureDrone}>{f.drone_id || "unknown"}</span>
            <span className={styles.failureT}>t={f.t || 0}s</span>
          </div>
        );
      })}
    </div>
  );
};

export default FailureTimeline;
