import React from 'react'
import styles from '@/styles/console.module.css'

interface ConsoleKVBarProps {
  coverage: number
  avgEntropy: string
  auctions: number
  dropouts: number
  elapsed: number
  bftRounds: number
  meshMessages: number
  survivorReceipts: number
}

const ConsoleKVBar: React.FC<ConsoleKVBarProps> = ({
  coverage,
  avgEntropy,
  auctions,
  dropouts,
  elapsed,
  bftRounds,
  meshMessages,
  survivorReceipts,
}) => {
  const items = [
    { label: 'Coverage', value: `${coverage}%`, variant: 'g' as const },
    { label: 'Avg Entropy', value: avgEntropy, variant: 'a' as const },
    { label: 'Auctions', value: String(auctions) },
    { label: 'Dropouts', value: String(dropouts) },
    { label: 'Elapsed', value: `${elapsed}s` },
    { label: 'Consensus', value: String(bftRounds) },
    { label: 'Mesh Msgs', value: String(meshMessages) },
    { label: 'Survivor Rcpts', value: String(survivorReceipts), variant: 'g' as const },
  ]

  return (
    <div className={styles.kvBar}>
      {items.map((item) => (
        <div key={item.label} className={styles.kv}>
          <div className={styles.kvK}>{item.label}</div>
          <div className={`${styles.kvV} ${item.variant ? styles[item.variant] : ''}`}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  )
}

export default React.memo(ConsoleKVBar)
