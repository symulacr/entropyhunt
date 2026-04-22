import React from 'react'
import type { ToastState } from '@/types/console'
import styles from '@/styles/console.module.css'

interface ToastProps {
  toast: ToastState
}

const Toast: React.FC<ToastProps> = ({ toast }) => {
  return (
    <div className={`${styles.toast} ${toast.visible ? styles.show : ''} ${styles[toast.type]}`}>
      {toast.message}
    </div>
  )
}

export default React.memo(Toast)
