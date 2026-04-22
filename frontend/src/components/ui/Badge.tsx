import React from 'react';
import styles from './Badge.module.css';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'ok' | 'warn' | 'error';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  className = ''
}) => {
  const classes = [styles.badge, styles[variant], className].filter(Boolean).join(' ');
  return <span className={classes}>{children}</span>;
};
