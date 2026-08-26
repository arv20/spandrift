import { QuizProvider, useQuiz } from './state/quizState';
import { Layout } from './components/Layout';
import { LandingScreen } from './screens/LandingScreen';
import { QuestionScreen } from './screens/QuestionScreen';
import { ResultsScreen } from './screens/ResultsScreen';

function QuizRouter() {
  const { state } = useQuiz();

  switch (state.screen) {
    case 'landing':
      return <LandingScreen />;
    case 'quiz':
      return <QuestionScreen />;
    case 'results':
      return <ResultsScreen />;
    default:
      return <LandingScreen />;
  }
}

export function App() {
  return (
    <QuizProvider>
      <Layout>
        <QuizRouter />
      </Layout>
    </QuizProvider>
  );
}
