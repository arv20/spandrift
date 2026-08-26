import React, { useRef } from 'react';
import { useQuiz } from '../state/quizState';
import { Button } from '../components/Button';
import { LARP_COPY, NORMAL_COPY } from '../data/larpCopy';
import { CAREER_PATHS } from '../data/careerPaths';
import styles from './LandingScreen.module.css';

export const LandingScreen: React.FC = () => {
  const { state, dispatch } = useQuiz();
  const copy = state.larpMode ? LARP_COPY : NORMAL_COPY;
  
  const clickCountRef = useRef(0);
  const lastClickTimeRef = useRef(0);

  const handleEasterEggClick = () => {
    const now = Date.now();
    if (now - lastClickTimeRef.current > 2000) {
      clickCountRef.current = 1;
    } else {
      clickCountRef.current += 1;
    }
    lastClickTimeRef.current = now;

    if (clickCountRef.current >= 5) {
      dispatch({ type: 'TOGGLE_LARP' });
      clickCountRef.current = 0;
    }
  };

  return (
    <div className={styles.landingWrapper}>
      {/* Wayfinding Header Brief */}
      <div className={styles.heroSection}>
        <div className={styles.metaRow}>
          <button 
            type="button" 
            className={styles.coordBadge} 
            onClick={handleEasterEggClick}
            aria-label="Wayfinding coordinate marker"
            title="Dublin Tech Club // Waypoint 37.7022° N"
          >
            <span>DUBLIN_CA // 37.7022° N</span>
            {state.larpMode && <span className={styles.larpTag}>[CARTOGRAPHY_MODE]</span>}
          </button>
          <span className={styles.routeTag}>STEM_EXPLORATION_V2</span>
        </div>

        <h1 className={styles.mainTitle}>
          {copy.landingTitle}
        </h1>

        <p className={styles.leadParagraph}>
          A 10-stop decision tree built for Dublin high-school students to map their natural problem-solving instincts to concrete engineering, research, and technical disciplines.
        </p>

        <div className={styles.specsGrid}>
          <div className={styles.specCard}>
            <span className={styles.specLabel}>TOTAL STOPS</span>
            <strong className={styles.specValue}>10 Waypoints</strong>
          </div>
          <div className={styles.specCard}>
            <span className={styles.specLabel}>ESTIMATED TIME</span>
            <strong className={styles.specValue}>60–90 Seconds</strong>
          </div>
          <div className={styles.specCard}>
            <span className={styles.specLabel}>OUTCOMES</span>
            <strong className={styles.specValue}>6 STEM Tracks</strong>
          </div>
        </div>

        <div className={styles.actionBlock}>
          <Button 
            variant="primary" 
            size="lg" 
            prefixTag="[START]"
            onClick={() => dispatch({ type: 'START_QUIZ' })}
          >
            {copy.startButton}
          </Button>

          <span className={styles.noExpText}>
            {copy.noExperience}
          </span>
        </div>
      </div>

      {/* Right Column: Route Destinations Overview */}
      <aside className={styles.destinationsPanel}>
        <div className={styles.panelHeader}>
          <span className={styles.panelTitle}>AVAILABLE DESTINATIONS</span>
          <span className={styles.panelSubtitle}>[6 PATHWAYS]</span>
        </div>

        <div className={styles.pathsList}>
          {CAREER_PATHS.map(path => (
            <div key={path.id} className={styles.pathItem}>
              <div className={styles.pathItemHeader}>
                <span className={styles.pathBadge}>[{path.badge}]</span>
                <span className={styles.pathName}>{path.name}</span>
              </div>
              <p className={styles.pathTagline}>{path.tagline}</p>
            </div>
          ))}
        </div>

        <div className={styles.disclaimerBox}>
          <span className={styles.disclaimerLabel}>NOTE:</span>
          <p className={styles.disclaimerText}>
            {copy.disclaimer}
          </p>
        </div>
      </aside>
    </div>
  );
};
