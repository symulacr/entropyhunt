import React from 'react'
import styles from '@/styles/console.module.css'

interface ControlsProps {
  speed: number
  onSpeedChange: (value: number) => void
  disabled: boolean
}

const Controls: React.FC<ControlsProps> = ({ speed, onSpeedChange, disabled }) => {
  return (
    <div className={styles.controls}>
      <span className={styles.ctlLbl}>Speed</span>
      <input
        type="range"
        min={1}
        max={5}
        value={speed}
        className={styles.rangeInput}
        disabled={disabled}
        onChange={(e) => onSpeedChange(Number(e.target.value))}
      />
      <span className={styles.ctlLbl}>{speed}&times;</span>
    </div>
  )
}

export default React.memo(Controls)
