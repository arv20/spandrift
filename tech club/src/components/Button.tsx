import React from 'react';
import styles from './Button.module.css';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'route';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  prefixTag?: string;
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  prefixTag,
  children,
  className = '',
  disabled,
  ...props
}) => {
  const buttonClass = [
    styles.button,
    styles[variant],
    styles[size],
    fullWidth ? styles.fullWidth : '',
    disabled ? styles.disabled : '',
    className
  ].filter(Boolean).join(' ');

  return (
    <button className={buttonClass} disabled={disabled} {...props}>
      {prefixTag && <span className={styles.prefixTag}>{prefixTag}</span>}
      <span className={styles.label}>{children}</span>
    </button>
  );
};
