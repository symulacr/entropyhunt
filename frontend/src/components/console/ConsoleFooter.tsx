import React from 'react'
import styles from '@/styles/console.module.css'

interface ConsoleFooterProps {
  message: string
}

const ConsoleFooter: React.FC<ConsoleFooterProps> = ({ message }) => {
  return (
    <footer className={styles.footer}>
      <div className={styles.pulse} />
      <span aria-live="polite" aria-atomic="true">{message}</span>
    </footer>
  )
}

export default React.memo(ConsoleFooter)
