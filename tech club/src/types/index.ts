export type CareerPathId =
  | 'quantFinance'
  | 'softwareEng'
  | 'aiDataScience'
  | 'cybersecurity'
  | 'productUx'
  | 'techEntrepreneurship';

export interface AnswerOption {
  text: string;
  code?: string; // e.g. "FORK_A", "FORK_B"
  weights: Partial<Record<CareerPathId, number>>;
}

export interface Question {
  id: number;
  stopIndex: string; // e.g. "STOP 01 // 10"
  category: string;  // e.g. "PROJECT ARCHITECTURE"
  text: string;
  contextNote?: string;
  answers: [AnswerOption, AnswerOption, AnswerOption, AnswerOption];
}

export interface CareerPath {
  id: CareerPathId;
  code: string; // e.g. "ROUTE_SWE", "ROUTE_SEC"
  name: string;
  badge: string; // e.g. "[SYS-ENG]"
  accentColor: string; // token reference
  tagline: string;
  description: string;
  whyItFits: string;
  typicalProblems: string[];
  skills: string[];
  tools: [string, string, string];
  starterProject: string;
  clubTrack: string;
}

export interface QuizResult {
  primary: { path: CareerPath; score: number; percentage: number };
  secondary: { path: CareerPath; score: number; percentage: number }[];
  allScores: Record<CareerPathId, number>;
  routeTrace: { stop: number; answerIndex: number; category: string }[];
}

export type Screen = 'landing' | 'quiz' | 'results';

export interface QuizState {
  screen: Screen;
  currentQuestion: number;
  answers: (number | null)[];
  larpMode: boolean;
  result: QuizResult | null;
}
