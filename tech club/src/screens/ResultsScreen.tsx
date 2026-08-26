import React, { useEffect, useState } from 'react';
import { useQuiz } from '../state/quizState';
import { Button } from '../components/Button';
import { LARP_COPY, NORMAL_COPY } from '../data/larpCopy';
import { QUESTIONS } from '../data/questions';
import { CAREER_PATHS, CAREER_PATH_PRIORITY } from '../data/careerPaths';
import { calculateResults } from '../scoring/calculateResults';
import styles from './ResultsScreen.module.css';

export const ResultsScreen: React.FC = () => {
  const { state, dispatch } = useQuiz();
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);

  const copy = state.larpMode ? LARP_COPY : NORMAL_COPY;

  useEffect(() => {
    if (!state.result) {
      const result = calculateResults(
        state.answers,
        QUESTIONS,
        CAREER_PATHS,
        CAREER_PATH_PRIORITY
      );
      dispatch({ type: 'SET_RESULT', payload: result });
    }
  }, [state.result, state.answers, dispatch]);

  useEffect(() => {
    if (state.result) {
      const timer = setTimeout(() => {
        setRevealed(true);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [state.result]);

  const handleCopy = async () => {
    if (!state.result) return;
    const { primary, secondary } = state.result;
    
    const text = `My Dublin Tech Club path is:\n\n${primary.path.emoji} ${primary.path.name} (${primary.percentage}% Match)\n\nSecondary Matches:\n- ${secondary[0].path.name} (${secondary[0].percentage}%)\n- ${secondary[1].path.name} (${secondary[1].percentage}%)\n\nStarter Project: ${primary.path.starterProject}\n\nCheck out Dublin Tech Club!`;
    
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  const handleRetake = () => {
    dispatch({ type: 'RESTART' });
  };

  if (!state.result || !revealed) {
    return (
      <div className={styles.loading}>
        <div className={styles.loadingText}>Calculating your path...</div>
      </div>
    );
  }

  const { primary, secondary } = state.result;
  const path = primary.path;

  return (
    <div className={styles.container}>
      <div 
        className={styles.revealWrapper}
        style={{ '--path-accent': path.accentColor } as React.CSSProperties}
      >
        <div className={styles.heroCard}>
          <div className={styles.heroEmoji}>{path.emoji}</div>
          <h1 className={styles.heroTitle}>{path.name}</h1>
          <div className={styles.heroPercentage}>{primary.percentage}% Match</div>
          <div className={styles.heroTagline}>"{path.tagline}"</div>
          <p className={styles.heroDescription}>{path.whyItFits}</p>
        </div>

        <div>
          <div className={styles.secondaryLabel}>Secondary Matches</div>
          <div className={styles.secondarySection}>
            {secondary.slice(0, 2).map((sec, index) => (
              <div key={index} className={styles.secondaryCard}>
                <div className={styles.secondaryEmoji}>{sec.path.emoji}</div>
                <div className={styles.secondaryName}>{sec.path.name}</div>
                <div className={styles.secondaryPercentage}>{sec.percentage}% Match</div>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>What You'd Work On</h2>
          <ul className={styles.problemsList}>
            {path.typicalProblems.map((problem, idx) => (
              <li key={idx} className={styles.problemItem}>{problem}</li>
            ))}
          </ul>
        </div>

        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>Skills to Explore</h2>
          <div className={styles.skillsGrid}>
            {path.skills.map((skill, idx) => (
              <span key={idx} className={styles.skillPill}>{skill}</span>
            ))}
          </div>
        </div>

        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>Tools to Try</h2>
          <div className={styles.toolsGrid}>
            {path.tools.map((tool, idx) => (
              <span key={idx} className={styles.toolItem}>{tool}</span>
            ))}
          </div>
        </div>

        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>Your Starter Project</h2>
          <div className={styles.starterProject}>
            {path.starterProject}
          </div>
        </div>

        <div className={styles.clubSection}>
          <h2 className={styles.sectionTitle}>How Dublin Tech Club Can Help</h2>
          <ul className={styles.clubBenefitsList}>
            <li className={styles.clubBenefit}>Compete in hackathons</li>
            <li className={styles.clubBenefit}>Build portfolio projects</li>
            <li className={styles.clubBenefit}>Meet industry professionals</li>
            <li className={styles.clubBenefit}>Gain career and possible internship exposure</li>
            <li className={styles.clubBenefit}>Work with teammates</li>
            <li className={styles.clubBenefit}>Earn volunteer hours through community outreach</li>
            <li className={styles.clubBenefit}>Teach or mentor younger students through technology activities</li>
          </ul>
          
          <div className={styles.clubLinks}>
            <div>📍 Meetings: [MEETING INFORMATION]</div>
            <div>🔗 Join Link: [JOIN LINK]</div>
            <div>📸 Instagram: [INSTAGRAM HANDLE]</div>
            <div className={styles.qrPlaceholder}>[QR CODE]</div>
          </div>
          
          <p className={styles.clubDisclaimer}>
            Note: Dublin Tech Club does not guarantee internships or specific career outcomes.
          </p>
        </div>

        <div className={styles.actions}>
          <Button variant="secondary" onClick={handleRetake}>
            {copy.retakeButton}
          </Button>
          <Button variant="primary" onClick={handleCopy}>
            {copied ? 'Copied!' : copy.copyButton}
          </Button>
        </div>

        <p className={styles.disclaimer}>
          This quiz is an exploration tool — not a scientific assessment or definitive career recommendation.
        </p>
      </div>
    </div>
  );
};
