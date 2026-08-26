import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';
import { QuizState, QuizResult } from '../types';

export type QuizAction =
  | { type: 'START_QUIZ' }
  | { type: 'ANSWER_QUESTION'; payload: { questionIndex: number; answerIndex: number } }
  | { type: 'NEXT_QUESTION' }
  | { type: 'PREV_QUESTION' }
  | { type: 'RESTART' }
  | { type: 'TOGGLE_LARP' }
  | { type: 'SET_RESULT'; payload: QuizResult }
  | { type: 'RESTORE_STATE'; payload: QuizState };

const initialState: QuizState = {
  screen: 'landing',
  currentQuestion: 0,
  answers: Array(10).fill(null),
  larpMode: false,
  result: null
};

export const QuizContext = createContext<{
  state: QuizState;
  dispatch: React.Dispatch<QuizAction>;
}>({
  state: initialState,
  dispatch: () => null
});

function quizReducer(state: QuizState, action: QuizAction): QuizState {
  switch (action.type) {
    case 'START_QUIZ':
      return {
        ...state,
        screen: 'quiz',
        currentQuestion: 0
      };
    case 'ANSWER_QUESTION': {
      const newAnswers = [...state.answers];
      newAnswers[action.payload.questionIndex] = action.payload.answerIndex;
      return {
        ...state,
        answers: newAnswers
      };
    }
    case 'NEXT_QUESTION': {
      const nextQ = state.currentQuestion + 1;
      if (nextQ >= 10) {
        return {
          ...state,
          currentQuestion: 9,
          screen: 'results'
        };
      }
      return {
        ...state,
        currentQuestion: nextQ
      };
    }
    case 'PREV_QUESTION':
      return {
        ...state,
        currentQuestion: Math.max(0, state.currentQuestion - 1)
      };
    case 'RESTART':
      return {
        ...initialState,
        larpMode: state.larpMode // Preserve larp mode preference
      };
    case 'TOGGLE_LARP':
      return {
        ...state,
        larpMode: !state.larpMode
      };
    case 'SET_RESULT':
      return {
        ...state,
        result: action.payload
      };
    case 'RESTORE_STATE':
      return action.payload;
    default:
      return state;
  }
}

const LOCAL_STORAGE_KEY = 'techpath-quiz-state';

export const QuizProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(quizReducer, initialState);

  // Load from local storage on mount
  useEffect(() => {
    const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        dispatch({ type: 'RESTORE_STATE', payload: parsed });
      } catch (e) {
        console.error('Failed to parse quiz state from local storage', e);
      }
    }
  }, []);

  // Save to local storage on state change, handle clear on restart
  useEffect(() => {
    if (state.screen === 'landing' && state.answers.every(a => a === null)) {
      // It's effectively restarted/initial, so we can clear or overwrite with initial
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    } else {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(state));
    }
  }, [state]);

  return (
    <QuizContext.Provider value={{ state, dispatch }}>
      {children}
    </QuizContext.Provider>
  );
};

export const useQuiz = () => {
  const context = useContext(QuizContext);
  if (!context) {
    throw new Error('useQuiz must be used within a QuizProvider');
  }
  return context;
};
