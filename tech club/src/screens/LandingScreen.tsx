import React, { useRef } from 'react';
import { useQuiz } from '../state/quizState';
import { Button } from '../components/Button';
import { LARP_COPY, NORMAL_COPY } from '../data/larpCopy';
import styles from './LandingScreen.module.css';

export const LandingScreen: React.FC = () => {
  const { state, dispatch } = useQuiz();
  const copy = state.larpMode ? LARP_COPY : NORMAL_COPY;
  
  const clickCountRef = useRef(0);
  const lastClickTimeRef = useRef(0);

  const handleEasterEggClick = () => {
    const now = Date.now();
    // Reset click count if more than 2 seconds have passed since last click
    if (now - lastClickTimeRef.current > 2000) {
      clickCountRef.current = 1;
    } else {
      clickCountRef.current += 1;
    }
    
    lastClickTimeRef.current = now;

    if (clickCountRef.current >= 5) {
      dispatch({ type: 'TOGGLE_LARP' });
      clickCountRef.current = 0; // Reset after trigger
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>
          {copy.landingTitle}
          {state.larpMode && <span className={styles.larpIndicator}>✨</span>}
        </h1>
        <p className={styles.subtitle}>
          {copy.landingSubtitle} 
          <span className={styles.easterEgg} onClick={handleEasterEggClick} role="button" aria-label="Toggle special mode"> ⚡</span>
        </p>
      </div>

      <div className={styles.mainAction}>
        <div className={styles.startButtonWrapper}>
          <Button variant="primary" size="lg" onClick={() => dispatch({ type: 'START_QUIZ' })}>
            {copy.startButton}
          </Button>
        </div>
        <p className={styles.noExperience}>
          {copy.noExperience}
        </p>
      </div>

      <p className={styles.disclaimer}>
        This is an exploration tool — not a scientific assessment or definitive career recommendation.
      </p>
      
      <div className={styles.decorativeElements} aria-hidden="true">
        <div className={`${styles.dot} ${styles.dot1}`}></div>
        <div className={`${styles.dot} ${styles.dot2}`}></div>
        <div className={`${styles.dot} ${styles.dot3}`}></div>
      </div>
    </div>
  );
};
