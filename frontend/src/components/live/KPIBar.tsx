import React from "react";
import styles from "@/styles/live.module.css";

interface KPI {
  label: string;
  value: string;
  variant: "default" | "accent" | "ok" | "warn";
}

interface KPIBarProps {
  kpis: KPI[];
}

const KPIBar: React.FC<KPIBarProps> = ({ kpis }) => {
  return (
    <div className={styles.kpiBar}>
      {kpis.map((kpi) => (
        <div key={kpi.label} className={styles.kpi}>
          <div className={styles.kpiLabel}>{kpi.label}</div>
          <div className={`${styles.kpiValue} ${styles[kpi.variant]}`}>{kpi.value}</div>
        </div>
      ))}
    </div>
  );
};

export default KPIBar;
