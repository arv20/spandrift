export type CareerPathId = 'quantFinance' | 'softwareEng' | 'aiDataScience' | 'cybersecurity' | 'productUx' | 'techEntrepreneurship';

export interface AnswerOption {
  text: string;
  weights: Partial<Record<CareerPathId, number>>;
}

export interface Question {
  id: number;
  text: string;
  answers: [AnswerOption, AnswerOption, AnswerOption, AnswerOption];
}

export interface CareerPath {
  id: CareerPathId;
  name: string;
  emoji: string;
  accentColor: string;
  tagline: string;
  description: string;
  whyItFits: string;
  typicalProblems: string[];
  skills: string[];
  tools: [string, string, string];
  starterProject: string;
}

export interface QuizResult {
  primary: { path: CareerPath; score: number; percentage: number };
  secondary: { path: CareerPath; score: number; percentage: number }[];
  allScores: Record<CareerPathId, number>;
}

export type Screen = 'landing' | 'quiz' | 'results';

export interface QuizState {
  screen: Screen;
  currentQuestion: number;
  answers: (number | null)[];
  larpMode: boolean;
  result: QuizResult | null;
}
