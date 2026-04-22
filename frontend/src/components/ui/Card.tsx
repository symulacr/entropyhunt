import React from 'react';
import styles from './Card.module.css';

export interface CardProps {
  label: string;
  value: string;
  note?: string;
  className?: string;
}

export const Card: React.FC<CardProps> = ({ label, value, note, className = '' }) => {
  return (
    <div className={[styles.card, className].filter(Boolean).join(' ')}>
      <p className={styles.label}>{label}</p>
      <p className={styles.value}>{value}</p>
      {note && <p className={styles.note}>{note}</p>}
    </div>
  );
};
