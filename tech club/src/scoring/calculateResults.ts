import { Question, CareerPath, CareerPathId, QuizResult } from '../types';

export function calculateResults(
  answers: (number | null)[],
  questions: Question[],
  careerPaths: CareerPath[],
  priorityOrder: CareerPathId[]
): QuizResult {
  const scores: Record<CareerPathId, number> = {
    quantFinance: 0,
    softwareEng: 0,
    aiDataScience: 0,
    cybersecurity: 0,
    productUx: 0,
    techEntrepreneurship: 0
  };

  const maxPossibleScores: Record<CareerPathId, number> = {
    quantFinance: 0,
    softwareEng: 0,
    aiDataScience: 0,
    cybersecurity: 0,
    productUx: 0,
    techEntrepreneurship: 0
  };

  answers.forEach((answerIndex, index) => {
    if (answerIndex === null || answerIndex === undefined) return;
    
    const question = questions[index];
    if (!question) return;

    // Add points for the chosen answer
    const chosenAnswer = question.answers[answerIndex];
    if (chosenAnswer && chosenAnswer.weights) {
      Object.entries(chosenAnswer.weights).forEach(([pathId, weight]) => {
        scores[pathId as CareerPathId] += weight;
      });
    }

    // Calculate max possible points for each path for this question
    priorityOrder.forEach(pathId => {
      let maxWeightForPath = 0;
      question.answers.forEach(ans => {
        const weight = ans.weights[pathId as CareerPathId] || 0;
        if (weight > maxWeightForPath) {
          maxWeightForPath = weight;
        }
      });
      maxPossibleScores[pathId] += maxWeightForPath;
    });
  });

  const getPercentage = (pathId: CareerPathId, score: number) => {
    const maxScore = Math.max(maxPossibleScores[pathId], 1);
    const rawPercentage = (score / maxScore) * 100;
    
    if (score === 0) return 0;
    
    return Math.max(1, Math.min(99, Math.round(rawPercentage)));
  };

  const sortedPaths = [...priorityOrder].sort((a, b) => {
    if (scores[a] !== scores[b]) {
      return scores[b] - scores[a];
    }
    // Tie breaker
    return priorityOrder.indexOf(a) - priorityOrder.indexOf(b);
  });

  const getPathData = (pathId: CareerPathId) => {
    const path = careerPaths.find(p => p.id === pathId);
    if (!path) throw new Error(`Career path not found: ${pathId}`);
    return {
      path,
      score: scores[pathId],
      percentage: getPercentage(pathId, scores[pathId])
    };
  };

  return {
    primary: getPathData(sortedPaths[0]),
    secondary: [
      getPathData(sortedPaths[1]),
      getPathData(sortedPaths[2])
    ],
    allScores: scores
  };
}
