import React from "react";
import type { ConsensusRound } from "@/types/live";
import styles from "@/styles/live.module.css";

interface ConsensusPanelProps {
  consensus: ConsensusRound[];
}

const ConsensusPanel: React.FC<ConsensusPanelProps> = ({ consensus }) => {
  if (!consensus || !consensus.length) {
    return (
      <div className={styles.stateMsgWaiting}>
        <div className={styles.stateMsgContent}>No consensus rounds recorded</div>
      </div>
    );
  }

  return (
    <div>
      {[...consensus].reverse().map((round) => {
        const cell = round.cell ? `[${round.cell[0]},${round.cell[1]}]` : "--";
        return (
          <div key={round.round_id} className={styles.consensusRow}>
            <span className={styles.consensusId}>#{round.round_id || 0}</span>
            <span className={styles.consensusCell}>{cell}</span>
            <span className={styles.consensusVotes}>
              {round.vote_count || 0} votes &middot; {round.status || "unknown"}
            </span>
          </div>
        );
      })}
    </div>
  );
};

export default ConsensusPanel;
