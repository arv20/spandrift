import { describe, it, expect } from 'vitest';
import { calculateResults } from './calculateResults';
import { QUESTIONS } from '../data/questions';
import { CAREER_PATHS, CAREER_PATH_PRIORITY } from '../data/careerPaths';

describe('calculateResults', () => {
  it('calculates the expected primary path for a known set of answers', () => {
    // Picking answers heavily weighted towards software engineering
    const answers = [0, 1, 2, 1, 0, 3, 0, 0, 0, 0];
    const result = calculateResults(answers, QUESTIONS, CAREER_PATHS, CAREER_PATH_PRIORITY);
    
    expect(result.primary.path.id).toBe('softwareEng');
    expect(result.primary.percentage).toBeGreaterThan(0);
    expect(result.routeTrace.length).toBe(10);
  });

  it('breaks ties using the priority order', () => {
    const mockQuestions = [
      {
        id: 1,
        stopIndex: 'STOP 01 // 10',
        category: 'TEST',
        text: 'Test',
        answers: [
          { text: 'A', code: 'FORK_A', weights: { quantFinance: 5, softwareEng: 5 } },
          { text: 'B', code: 'FORK_B', weights: {} },
          { text: 'C', code: 'FORK_C', weights: {} },
          { text: 'D', code: 'FORK_D', weights: {} }
        ]
      }
    ] as any;
    
    const answers = [0];
    const result = calculateResults(answers, mockQuestions, CAREER_PATHS, CAREER_PATH_PRIORITY);
    
    expect(result.primary.path.id).toBe('quantFinance'); // First in priority order
  });

  it('ensures all paths can be reached as primary', () => {
    CAREER_PATH_PRIORITY.forEach(pathId => {
      const answers = QUESTIONS.map(q => {
        let bestAnsIndex = 0;
        let maxWeight = -1;
        q.answers.forEach((ans, i) => {
          const weight = (ans.weights as any)[pathId] || 0;
          if (weight > maxWeight) {
            maxWeight = weight;
            bestAnsIndex = i;
          }
        });
        return bestAnsIndex;
      });

      const result = calculateResults(answers, QUESTIONS, CAREER_PATHS, CAREER_PATH_PRIORITY);
      expect(result.primary.path.id).toBe(pathId);
    });
  });

  it('recalculates correctly if an answer changes', () => {
    const initialAnswers = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    const initialResult = calculateResults(initialAnswers, QUESTIONS, CAREER_PATHS, CAREER_PATH_PRIORITY);
    
    const changedAnswers = [1, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    const changedResult = calculateResults(changedAnswers, QUESTIONS, CAREER_PATHS, CAREER_PATH_PRIORITY);
    
    expect(initialResult.allScores).not.toEqual(changedResult.allScores);
  });

  it('skips null answers and generates partial routeTrace', () => {
    const answers = [0, null, 0, null, 0, null, null, null, null, null];
    const result = calculateResults(answers, QUESTIONS, CAREER_PATHS, CAREER_PATH_PRIORITY);
    
    expect(result.primary).toBeDefined();
    expect(result.primary.percentage).toBeGreaterThan(0);
    expect(result.primary.percentage).toBeLessThanOrEqual(99);
    expect(result.routeTrace.length).toBe(3);
  });
});
