import React, { useEffect } from 'react';
import { useQuiz } from '../state/quizState';
import { Button } from '../components/Button';
import { ProgressBar } from '../components/ProgressBar';
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

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input
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
        if (selectedAnswer !== null) {
          dispatch({ type: 'NEXT_QUESTION' });
        }
      }

      // Keys 1-4 for answering
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
    <div className={styles.container}>
      <ProgressBar 
        current={currentQuestion} 
        total={QUESTIONS.length} 
        label={copy.questionLabel} 
      />
      
      <div key={currentQuestion} className={styles.questionContent}>
        <h2 className={styles.questionText}>{question.text}</h2>
        
        <div className={styles.answersGrid}>
          {question.answers.map((answer, index) => {
            const isSelected = selectedAnswer === index;
            return (
              <button
                key={index}
                className={`${styles.answerCard} ${isSelected ? styles.answerCardSelected : ''}`}
                onClick={() => dispatch({
                  type: 'ANSWER_QUESTION',
                  payload: { questionIndex: currentQuestion, answerIndex: index }
                })}
                aria-pressed={isSelected}
              >
                <div className={styles.answerNumber}>{index + 1}</div>
                <div className={styles.answerText}>{answer.text}</div>
              </button>
            );
          })}
        </div>
      </div>

      <div className={styles.navigation}>
        <div className={styles.navLeft}>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => dispatch({ type: 'PREV_QUESTION' })}
            disabled={isFirstQuestion}
          >
            {copy.backButton}
          </Button>
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => dispatch({ type: 'RESTART' })}
          >
            {copy.restartButton}
          </Button>
        </div>
        
        <Button 
          variant="primary" 
          size="md"
          onClick={() => dispatch({ type: 'NEXT_QUESTION' })}
          disabled={selectedAnswer === null}
        >
          {isLastQuestion ? (larpMode ? 'Reveal Destiny' : 'See Results') : copy.nextButton}
        </Button>
      </div>
    </div>
  );
};
