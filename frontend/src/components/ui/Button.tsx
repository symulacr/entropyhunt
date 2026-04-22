import React from 'react';
import styles from './Button.module.css';

export interface ButtonProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost';
  href?: string;
  onClick?: () => void;
  icon?: React.ReactNode;
  className?: string;
  ariaLabel?: string;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'secondary',
  href,
  onClick,
  icon,
  className = '',
  ariaLabel
}) => {
  const classes = [styles.button, styles[variant], className].filter(Boolean).join(' ');

  const content = (
    <>
      <span className={styles.content}>{children}</span>
      {icon && (
        <span className={styles.iconWrap} aria-hidden="true">
          {icon}
        </span>
      )}
    </>
  );

  if (href) {
    return (
      <a
        href={href}
        className={classes}
        aria-label={ariaLabel}
      >
        {content}
      </a>
    );
  }

  return (
    <button
      type="button"
      className={classes}
      onClick={onClick}
      aria-label={ariaLabel}
    >
      {content}
    </button>
  );
};
