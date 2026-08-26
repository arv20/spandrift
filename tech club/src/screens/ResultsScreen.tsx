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

  const handleCopy = async () => {
    if (!state.result) return;
    const { primary, secondary } = state.result;
    
    const text = [
      `DUBLIN TECH CLUB // TECH PATH ANALYSIS`,
      `=======================================`,
      `PRIMARY DESTINATION: [${primary.path.badge}] ${primary.path.name}`,
      `ALIGNMENT SCORE: ${primary.percentage}%`,
      `TAGLINE: "${primary.path.tagline}"`,
      ``,
      `SECONDARY BRANCHES:`,
      `- [${secondary[0].path.badge}] ${secondary[0].path.name} (${secondary[0].percentage}%)`,
      `- [${secondary[1].path.badge}] ${secondary[1].path.name} (${secondary[1].percentage}%)`,
      ``,
      `RECOMMENDED STARTER PROJECT:`,
      `${primary.path.starterProject}`,
      ``,
      `DUBLIN TECH CLUB TRACK:`,
      `${primary.path.clubTrack}`,
      `=======================================`,
      `Explore with Dublin Tech Club: arv20.github.io/opensourceproject/`
    ].join('\n');
    
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch (err) {
      console.error('Failed to copy route summary', err);
    }
  };

  const handleRetake = () => {
    dispatch({ type: 'RESTART' });
  };

  if (!state.result) {
    return (
      <div className={styles.calculatingState}>
        <span className={styles.calculatingMeta}>WAYFINDING ENGINE // RUNNING TRACE</span>
        <h2 className={styles.calculatingTitle}>Mapping Decision Route...</h2>
      </div>
    );
  }

  const { primary, secondary, routeTrace } = state.result;
  const path = primary.path;

  return (
    <div className={styles.resultsRoot}>
      {/* Route Header Banner */}
      <div className={styles.resultsHeader}>
        <div className={styles.headerMetaRow}>
          <span className={styles.routeResolvedTag}>ROUTE RESOLVED // 10 OF 10 STOPS EVALUATED</span>
          <span className={styles.coordStamp}>37.7022° N, 121.9358° W</span>
        </div>
        <h1 className={styles.resultsMainTitle}>{copy.resultTitle}</h1>
      </div>

      {/* Signature Moment: The Wayfinding Route Trace Diagram */}
      <section className={styles.routeTraceSection} aria-label="Route decision tree diagram">
        <div className={styles.traceHeader}>
          <span className={styles.traceTitle}>YOUR DECISION TRACE</span>
          <span className={styles.traceSubtitle}>[10 WAYPOINTS → 1 DESTINATION]</span>
        </div>

        <div className={styles.traceGrid}>
          {routeTrace.map((stopItem) => {
            const forkCode = `FORK_0${stopItem.answerIndex + 1}`;
            return (
              <div key={stopItem.stop} className={styles.traceStopNode}>
                <div className={styles.stopNodeIndex}>
                  <span className={styles.stopNum}>{stopItem.stop.toString().padStart(2, '0')}</span>
                  <span className={styles.stopFork}>{forkCode}</span>
                </div>
                <div className={styles.stopCategory}>{stopItem.category}</div>
              </div>
            );
          })}
          <div className={styles.traceDestinationNode}>
            <div className={styles.destBadge}>[{path.badge}]</div>
            <div className={styles.destLabel}>DESTINATION</div>
          </div>
        </div>
      </section>

      {/* Primary Destination Hero Card */}
      <section className={styles.primaryHeroCard}>
        <div className={styles.heroTopMeta}>
          <span className={styles.primaryBadge}>[{path.badge}] PRIMARY ALIGNMENT</span>
          <span className={styles.matchScore}>{primary.percentage}% MATCH</span>
        </div>

        <h2 className={styles.primaryName}>{path.name}</h2>
        <p className={styles.primaryTagline}>"{path.tagline}"</p>

        <div className={styles.analysisBox}>
          <span className={styles.analysisLabel}>DECISION ALIGNMENT ANALYSIS</span>
          <p className={styles.analysisText}>{path.whyItFits}</p>
        </div>
      </section>

      {/* Secondary Divergences */}
      <section className={styles.secondarySection}>
        <div className={styles.sectionHeaderMeta}>
          <span className={styles.sectionMetaTitle}>SECONDARY BRANCHES</span>
          <span className={styles.sectionMetaSubtitle}>[ADJACENT DISCIPLINES]</span>
        </div>

        <div className={styles.secondaryGrid}>
          {secondary.slice(0, 2).map((sec) => (
            <div key={sec.path.id} className={styles.secondaryCard}>
              <div className={styles.secTopRow}>
                <span className={styles.secBadge}>[{sec.path.badge}]</span>
                <span className={styles.secScore}>{sec.percentage}% MATCH</span>
              </div>
              <h3 className={styles.secName}>{sec.path.name}</h3>
              <p className={styles.secTagline}>{sec.path.tagline}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Technical Problems Breakdown */}
      <section className={styles.detailsSection}>
        <div className={styles.sectionHeaderMeta}>
          <span className={styles.sectionMetaTitle}>REPRESENTATIVE PROBLEMS SOLVED</span>
          <span className={styles.sectionMetaSubtitle}>[ENGINEERING SCOPE]</span>
        </div>

        <ul className={styles.problemsList}>
          {path.typicalProblems.map((prob, idx) => (
            <li key={idx} className={styles.problemItem}>
              <span className={styles.problemIndex}>0{idx + 1}</span>
              <span className={styles.problemText}>{prob}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Skills & Tools Grid */}
      <div className={styles.skillsAndToolsGrid}>
        <section className={styles.subCard}>
          <div className={styles.sectionHeaderMeta}>
            <span className={styles.sectionMetaTitle}>SKILLS & SUBJECTS</span>
          </div>
          <div className={styles.tagsContainer}>
            {path.skills.map((skill, idx) => (
              <span key={idx} className={styles.tagItem}>{skill}</span>
            ))}
          </div>
        </section>

        <section className={styles.subCard}>
          <div className={styles.sectionHeaderMeta}>
            <span className={styles.sectionMetaTitle}>RECOMMENDED STARTER TOOLS</span>
          </div>
          <div className={styles.toolsContainer}>
            {path.tools.map((tool, idx) => (
              <span key={idx} className={styles.toolItem}>
                <span className={styles.toolDot} />
                {tool}
              </span>
            ))}
          </div>
        </section>
      </div>

      {/* Recommended Starter Project */}
      <section className={styles.starterProjectSection}>
        <div className={styles.sectionHeaderMeta}>
          <span className={styles.sectionMetaTitle}>CONCRETE STARTER PROJECT</span>
          <span className={styles.sectionMetaSubtitle}>[HANDS-ON MILESTONE]</span>
        </div>
        <div className={styles.projectBody}>
          <p className={styles.projectText}>{path.starterProject}</p>
        </div>
      </section>

      {/* Dublin Tech Club Opportunities */}
      <section className={styles.clubSection}>
        <div className={styles.sectionHeaderMeta}>
          <span className={styles.sectionMetaTitle}>HOW DUBLIN TECH CLUB HELPS</span>
          <span className={styles.sectionMetaSubtitle}>[COMMUNITY & INCUBATION]</span>
        </div>

        <div className={styles.clubTrackHighlight}>
          <span className={styles.trackLabel}>RECOMMENDED CLUB TRACK:</span>
          <strong className={styles.trackName}>{path.clubTrack}</strong>
        </div>

        <div className={styles.clubBenefitsGrid}>
          <div className={styles.benefitItem}>
            <span className={styles.benefitMarker}>[01]</span>
            <span>Compete in regional hackathons with structured squads</span>
          </div>
          <div className={styles.benefitItem}>
            <span className={styles.benefitMarker}>[02]</span>
            <span>Build deployable open-source portfolio repositories</span>
          </div>
          <div className={styles.benefitItem}>
            <span className={styles.benefitMarker}>[03]</span>
            <span>Participate in technical Q&As with industry engineers</span>
          </div>
          <div className={styles.benefitItem}>
            <span className={styles.benefitMarker}>[04]</span>
            <span>Gain career pathways & potential internship exposure</span>
          </div>
          <div className={styles.benefitItem}>
            <span className={styles.benefitMarker}>[05]</span>
            <span>Collaborate on cross-functional engineering teams</span>
          </div>
          <div className={styles.benefitItem}>
            <span className={styles.benefitMarker}>[06]</span>
            <span>Earn volunteer hours through STEM community outreach</span>
          </div>
          <div className={styles.benefitItem}>
            <span className={styles.benefitMarker}>[07]</span>
            <span>Teach & mentor younger students in introductory coding</span>
          </div>
        </div>

        <div className={styles.clubContactCard}>
          <div className={styles.contactFields}>
            <div className={styles.contactRow}>
              <span className={styles.contactLabel}>MEETING INFO:</span>
              <span className={styles.contactValue}>[MEETING INFORMATION]</span>
            </div>
            <div className={styles.contactRow}>
              <span className={styles.contactLabel}>CLUB PORTAL:</span>
              <span className={styles.contactValue}>[JOIN LINK]</span>
            </div>
            <div className={styles.contactRow}>
              <span className={styles.contactLabel}>INSTAGRAM:</span>
              <span className={styles.contactValue}>[INSTAGRAM HANDLE]</span>
            </div>
          </div>

          <div className={styles.qrBox}>
            <div className={styles.qrPlaceholderBorder}>
              <span className={styles.qrText}>[QR CODE]</span>
            </div>
          </div>
        </div>

        <p className={styles.clubDisclaimerNote}>
          Note: Dublin Tech Club provides educational programming and project mentorship; it does not guarantee specific internships or commercial outcomes.
        </p>
      </section>

      {/* Actions */}
      <div className={styles.actionsRow}>
        <Button 
          variant="secondary" 
          size="md" 
          onClick={handleRetake}
          prefixTag="[↺]"
        >
          {copy.retakeButton}
        </Button>

        <Button 
          variant="primary" 
          size="md" 
          onClick={handleCopy}
          prefixTag={copied ? '[✓]' : '[EXPORT]'}
        >
          {copied ? 'Path Summary Copied' : copy.copyButton}
        </Button>
      </div>

      <p className={styles.footerDisclaimer}>
        {copy.disclaimer}
      </p>
    </div>
  );
};
