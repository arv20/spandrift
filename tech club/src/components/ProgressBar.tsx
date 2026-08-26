import React from 'react';
import styles from './ProgressBar.module.css';

interface ProgressBarProps {
  current: number; // 0-indexed current question
  total: number;
  label?: string; // e.g., "Question" or "Trial" for LARP mode
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  current,
  total,
  label = 'Question'
}) => {
  return (
    <div className={styles.container}>
      <div className={styles.label}>
        {label} {Math.min(current + 1, total)} of {total}
      </div>
      <div className={styles.track}>
        {Array.from({ length: total }).map((_, index) => {
          const isCompleted = index < current;
          const isCurrent = index === current;
          
          let segmentClass = styles.segment;
          if (isCompleted) segmentClass += ` ${styles.completed}`;
          if (isCurrent) segmentClass += ` ${styles.current}`;

          return <div key={index} className={segmentClass} />;
        })}
      </div>
    </div>
  );
};
