import React from 'react';
import { Button } from './Button';
import styles from './Hero.module.css';

export interface HeroProps {
  eyebrow: string;
  title: string;
  lede: string;
  primaryAction: {
    label: string;
    href: string;
    icon?: React.ReactNode;
  };
  secondaryAction: {
    label: string;
    href: string;
  };
}

export const Hero: React.FC<HeroProps> = ({
  eyebrow,
  title,
  lede,
  primaryAction,
  secondaryAction
}) => {
  return (
    <section className={styles.hero}>
      <div className={styles.content}>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h1>{title}</h1>
        <p className={styles.lede}>{lede}</p>
      </div>
      <div className={styles.actions}>
        <Button variant="primary" href={primaryAction.href} icon={primaryAction.icon}>
          {primaryAction.label}
        </Button>
        <Button variant="secondary" href={secondaryAction.href}>
          {secondaryAction.label}
        </Button>
      </div>
    </section>
  );
};
