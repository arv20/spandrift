import React, { useEffect } from 'react';
import { useQuiz } from '../state/quizState';
import { Button } from '../components/Button';
import { RouteRail } from '../components/RouteRail';
import { QUESTIONS } from '../data/questions';
import { LARP_COPY, NORMAL_COPY } from '../data/larpCopy';
import styles from './QuestionScreen.module.css';

export const QuestionScreen: React.FC = () => {
  const { state, dispatch } = useQuiz();
  const { currentQuestion, answers, larpMode } = state;
  const copy = larpMode ? LARP_COPY : NORMAL_COPY;
  
  const question = QUESTIONS[currentQuestion];
  const selectedAnswer = answers[currentQuestion];
  const isFirstQuestion = currentQuestion === 0;
  const isLastQuestion = currentQuestion === QUESTIONS.length - 1;

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        document.activeElement?.tagName === 'INPUT' || 
        document.activeElement?.tagName === 'TEXTAREA'
      ) {
        return;
      }

      if (e.key === 'Escape') {
        if (isFirstQuestion) {
          dispatch({ type: 'RESTART' });
        } else {
          dispatch({ type: 'PREV_QUESTION' });
        }
      }

      if (e.key === 'Enter') {
        if (selectedAnswer !== null && selectedAnswer !== undefined) {
          dispatch({ type: 'NEXT_QUESTION' });
        }
      }

      if (['1', '2', '3', '4'].includes(e.key)) {
        const index = parseInt(e.key, 10) - 1;
        if (index < question.answers.length) {
          dispatch({
            type: 'ANSWER_QUESTION',
            payload: { questionIndex: currentQuestion, answerIndex: index }
          });
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentQuestion, isFirstQuestion, selectedAnswer, dispatch, question.answers.length]);

  return (
    <div className={styles.questionScreenRoot}>
      {/* Top Navigational Route Rail */}
      <div className={styles.railWrapper}>
        <RouteRail 
          current={currentQuestion} 
          total={QUESTIONS.length} 
          label={copy.questionLabel}
          answeredStops={answers}
        />
      </div>

      {/* Asymmetric Split Body */}
      <div className={styles.splitBody}>
        {/* Left Column: Context & Prompt */}
        <div className={styles.promptColumn}>
          <div className={styles.categoryBadge}>
            <span className={styles.categoryCode}>[{question.category}]</span>
          </div>

          <h2 className={styles.questionText}>
            {question.text}
          </h2>

          {question.contextNote && (
            <p className={styles.contextNote}>
              {question.contextNote}
            </p>
          )}

          <div className={styles.keyboardHints} aria-hidden="true">
            <span className={styles.hintKey}>[1-4]</span> Select Fork
            <span className={styles.hintDivider}> · </span>
            <span className={styles.hintKey}>[ENTER]</span> Advance
            <span className={styles.hintDivider}> · </span>
            <span className={styles.hintKey}>[ESC]</span> Back
          </div>
        </div>

        {/* Right Column: Fork Options List */}
        <div className={styles.optionsColumn}>
          <div className={styles.optionsHeader}>
            <span className={styles.optionsTitle}>SELECT FORK</span>
            <span className={styles.optionsSubtitle}>[CHOOSE 1 OF 4]</span>
          </div>

          <div className={styles.optionsList} role="radiogroup" aria-label="Route fork options">
            {question.answers.map((answer, index) => {
              const isSelected = selectedAnswer === index;
              const forkCode = answer.code || `FORK_0${index + 1}`;

              return (
                <button
                  key={index}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  className={`${styles.optionCard} ${isSelected ? styles.optionCardSelected : ''}`}
                  onClick={() => dispatch({
                    type: 'ANSWER_QUESTION',
                    payload: { questionIndex: currentQuestion, answerIndex: index }
                  })}
                >
                  <div className={styles.optionNotch}>
                    <span className={styles.optionIndex}>0{index + 1}</span>
                    <span className={styles.forkTag}>[{forkCode}]</span>
                  </div>

                  <div className={styles.optionText}>
                    {answer.text}
                  </div>

                  <div className={styles.selectionIndicator} aria-hidden="true">
                    <span className={styles.indicatorDot} />
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Navigation Footer Controls */}
      <div className={styles.navBar}>
        <div className={styles.navLeft}>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => dispatch({ type: 'PREV_QUESTION' })}
            disabled={isFirstQuestion}
            prefixTag="[←]"
          >
            {copy.backButton}
          </Button>

          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => dispatch({ type: 'RESTART' })}
            prefixTag="[×]"
          >
            {copy.restartButton}
          </Button>
        </div>
        
        <Button 
          variant={isLastQuestion ? 'route' : 'primary'}
          size="md"
          onClick={() => dispatch({ type: 'NEXT_QUESTION' })}
          disabled={selectedAnswer === null || selectedAnswer === undefined}
          prefixTag={isLastQuestion ? '[DESTINATION]' : '[→]'}
        >
          {isLastQuestion ? (larpMode ? 'Survey Destination' : 'See Your Path') : copy.nextButton}
        </Button>
      </div>
    </div>
  );
};
