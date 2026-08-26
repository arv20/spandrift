import React from 'react';
import { useQuiz } from '../state/quizState';
import styles from './Layout.module.css';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { state, dispatch } = useQuiz();

  return (
    <div className={styles.layoutRoot}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brandGroup}>
            <button 
              type="button" 
              className={styles.brandTitle}
              onClick={() => state.screen !== 'landing' && dispatch({ type: 'RESTART' })}
              title="Return to start"
            >
              <span className={styles.clubName}>DUBLIN TECH CLUB</span>
              <span className={styles.breadcrumbSlash}> / </span>
              <span className={styles.appName}>FIND YOUR TECH PATH</span>
            </button>
          </div>

          <div className={styles.headerMeta}>
            <span className={styles.statusIndicator}>
              <span className={styles.statusDot} />
              <span className={styles.statusText}>
                {state.screen === 'landing' && 'SYSTEM READY'}
                {state.screen === 'quiz' && `ROUTE ACTIVE // STOP ${(state.currentQuestion + 1).toString().padStart(2, '0')}`}
                {state.screen === 'results' && 'DESTINATION MAPPED'}
              </span>
            </span>
          </div>
        </div>
      </header>

      <main className={styles.mainContainer}>
        {children}
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <span className={styles.footerTag}>
            DUBLIN HIGH SCHOOL STEM INITIATIVE
          </span>
          <span className={styles.footerCopyright}>
            EST. 2026 // OPEN SOURCE EXPLORATION
          </span>
        </div>
      </footer>
    </div>
  );
};
