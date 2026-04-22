import React from 'react';
import { Badge } from './Badge';
import styles from './SectionHeader.module.css';

export interface SectionHeaderProps {
  title: string;
  badge?: string;
  badgeVariant?: 'default' | 'ok' | 'warn' | 'error';
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  title,
  badge,
  badgeVariant = 'default',
  className = ''
}) => {
  return (
    <div className={[styles.header, className].filter(Boolean).join(' ')}>
      <h2>{title}</h2>
      {badge && <Badge variant={badgeVariant}>{badge}</Badge>}
    </div>
  );
};
