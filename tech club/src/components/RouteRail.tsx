import React from 'react';
import styles from './RouteRail.module.css';

interface RouteRailProps {
  current: number; // 0-indexed (0 to 9)
  total: number;
  label?: string;
  onSelectStop?: (index: number) => void;
  answeredStops?: (number | null)[];
}

export const RouteRail: React.FC<RouteRailProps> = ({
  current,
  total,
  label = 'STOP',
  onSelectStop,
  answeredStops = []
}) => {
  const currentStopDisplay = (current + 1).toString().padStart(2, '0');
  const totalStopsDisplay = total.toString().padStart(2, '0');
  const progressPercent = ((current) / (total - 1)) * 100;

  return (
    <div className={styles.railContainer}>
      <div className={styles.headerMeta}>
        <span className={styles.metaLabel}>{label}</span>
        <span className={styles.metaCounter}>
          <strong className={styles.currentNum}>{currentStopDisplay}</strong>
          <span className={styles.divider}> // </span>
          <span className={styles.totalNum}>{totalStopsDisplay}</span>
        </span>
      </div>

      {/* Visual Route Line with Waypoint Nodes */}
      <div className={styles.trackWrapper} role="progressbar" aria-valuenow={current + 1} aria-valuemin={1} aria-valuemax={total}>
        <div className={styles.trackLine}>
          <div 
            className={styles.fillLine} 
            style={{ '--progress-pct': `${progressPercent}%` } as React.CSSProperties}
          />
        </div>

        <div className={styles.nodesList}>
          {Array.from({ length: total }).map((_, index) => {
            const isCompleted = index < current;
            const isCurrent = index === current;
            const isAnswered = answeredStops[index] !== null && answeredStops[index] !== undefined;
            const isClickable = Boolean(onSelectStop && (isCompleted || isAnswered || index <= current));

            let nodeClass = styles.node;
            if (isCompleted) nodeClass += ` ${styles.nodeCompleted}`;
            if (isCurrent) nodeClass += ` ${styles.nodeCurrent}`;

            return (
              <button
                key={index}
                type="button"
                className={nodeClass}
                disabled={!isClickable}
                onClick={() => isClickable && onSelectStop && onSelectStop(index)}
                aria-label={`Go to Stop ${index + 1}`}
                title={`Stop ${index + 1}`}
              >
                <span className={styles.nodeDot} />
                <span className={styles.nodeLabel}>{(index + 1).toString().padStart(2, '0')}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
