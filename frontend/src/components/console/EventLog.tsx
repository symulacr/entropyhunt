import React from 'react'
import type { LogEvent } from '@/types/console'
import styles from '@/styles/console.module.css'

interface EventLogProps {
  events: LogEvent[]
}

const typeClassMap: Record<LogEvent['type'], string> = {
  bft: styles.logBft,
  ok: styles.logOk,
  err: styles.logErr,
  warn: styles.logWarn,
  info: styles.logInfo,
}

const EventLog: React.FC<EventLogProps> = ({ events }) => {
  return (
    <div className={styles.sideBlock} style={{ flex: 1 }}>
      <div className={styles.sideHead}>Event Log</div>
      <div className={styles.sideBody}>
        {events.map((event, index) => (
          <div key={`${event.t}-${index}`} className={styles.logLine}>
            <span className={`${styles.logType} ${typeClassMap[event.type] || styles.logInfo}`}>
              {event.type.toUpperCase()}
            </span>
            <span style={{ color: 'var(--text-muted)' }}> t={event.t}s </span>
            {event.msg}
          </div>
        ))}
      </div>
    </div>
  )
}

export default React.memo(EventLog)
