import { CareerPath, CareerPathId } from '../types';

export const CAREER_PATHS: CareerPath[] = [
  {
    id: 'quantFinance',
    name: 'Quant Finance',
    emoji: '📈',
    accentColor: '#10b981',
    tagline: 'Predict the markets using math and code.',
    description: 'You love finding hidden patterns in chaos. Quants use advanced mathematics, statistics, and programming to understand and predict financial markets.',
    whyItFits: 'Your analytical mindset and love for numbers make you a perfect fit for the high-stakes world of quantitative finance.',
    typicalProblems: ['Optimizing trading algorithms', 'Predicting stock market trends', 'Managing financial risk', 'Analyzing massive financial datasets'],
    skills: ['Mathematics', 'Statistics', 'Programming', 'Economics', 'Pattern Recognition'],
    tools: ['Python', 'Pandas', 'Excel'],
    starterProject: 'Build a simulated portfolio or a basic market-data analyzer in Python.'
  },
  {
    id: 'softwareEng',
    name: 'Software Engineering',
    emoji: '💻',
    accentColor: '#3b82f6',
    tagline: 'Build the digital world around us.',
    description: 'You are a builder at heart. Software engineers design, create, and maintain the applications and systems that power our daily lives.',
    whyItFits: 'You enjoy turning ideas into reality, writing clean logic, and the satisfaction of squashing a tricky bug.',
    typicalProblems: ['Designing scalable systems', 'Writing efficient code', 'Debugging complex issues', 'Collaborating on large codebases'],
    skills: ['Logic', 'Problem Solving', 'System Design', 'Debugging', 'Teamwork'],
    tools: ['JavaScript', 'React', 'Git'],
    starterProject: 'Create a personal productivity app, a simple web game, or a website for your school club.'
  },
  {
    id: 'aiDataScience',
    name: 'AI & Data Science',
    emoji: '🤖',
    accentColor: '#8b5cf6',
    tagline: 'Teach computers to learn and predict the future.',
    description: 'You are curious about how things work and love experimenting. AI specialists and Data Scientists extract insights from data and build intelligent models.',
    whyItFits: 'Your curiosity and knack for experimentation are exactly what\'s needed to uncover insights and build the next generation of AI.',
    typicalProblems: ['Training machine learning models', 'Extracting insights from messy data', 'Building recommendation systems', 'Automating decision-making'],
    skills: ['Experimentation', 'Pattern Recognition', 'Math', 'Curiosity', 'Data Analysis'],
    tools: ['Python', 'TensorFlow', 'Jupyter Notebooks'],
    starterProject: 'Analyze a public dataset to find trends, or build a simple image or text classifier.'
  },
  {
    id: 'cybersecurity',
    name: 'Cybersecurity',
    emoji: '🔒',
    accentColor: '#ef4444',
    tagline: 'Defend the digital realm from threats.',
    description: 'You love a good puzzle and outsmarting adversaries. Cybersecurity professionals protect systems, networks, and data from malicious attacks.',
    whyItFits: 'Your investigative nature and desire to understand complex systems make you an excellent defender in the digital world.',
    typicalProblems: ['Securing networks against hackers', 'Finding vulnerabilities in software', 'Investigating security breaches', 'Encrypting sensitive data'],
    skills: ['Investigation', 'Puzzle Solving', 'Attention to Detail', 'Systems Thinking', 'Ethics'],
    tools: ['Kali Linux', 'Wireshark', 'Bash'],
    starterProject: 'Build a password-strength analyzer or participate in a beginner CTF (Capture The Flag) challenge.'
  },
  {
    id: 'productUx',
    name: 'Product & UX',
    emoji: '🎨',
    accentColor: '#f59e0b',
    tagline: 'Design experiences that people love to use.',
    description: 'You are empathetic and visual. Product Managers and UX Designers focus on understanding user needs and creating intuitive, beautiful solutions.',
    whyItFits: 'Your empathy for users and visual communication skills ensure that technology is not just powerful, but accessible and enjoyable.',
    typicalProblems: ['Understanding user pain points', 'Creating wireframes and prototypes', 'Conducting user research', 'Balancing business and user needs'],
    skills: ['Empathy', 'Visual Design', 'Communication', 'Prototyping', 'User Research'],
    tools: ['Figma', 'Notion', 'User Interviews'],
    starterProject: 'Redesign a frustrating digital experience from your school or local community.'
  },
  {
    id: 'techEntrepreneurship',
    name: 'Tech Entrepreneurship',
    emoji: '🚀',
    accentColor: '#ec4899',
    tagline: 'Lead teams to turn big ideas into businesses.',
    description: 'You are a visionary and a leader. Tech entrepreneurs identify market gaps, assemble teams, and build products to solve real-world problems.',
    whyItFits: 'Your drive to identify problems, make decisions, and lead others will help you turn your tech ideas into successful ventures.',
    typicalProblems: ['Identifying market opportunities', 'Pitching ideas to investors', 'Leading cross-functional teams', 'Making strategic business decisions'],
    skills: ['Leadership', 'Pitching', 'Decision Making', 'Vision', 'Resilience'],
    tools: ['Pitch Decks', 'Business Model Canvas', 'Trello'],
    starterProject: 'Design and validate a tech product idea that solves a common problem for students.'
  }
];

export const CAREER_PATH_MAP: Record<CareerPathId, CareerPath> = CAREER_PATHS.reduce((acc, path) => {
  acc[path.id] = path;
  return acc;
}, {} as Record<CareerPathId, CareerPath>);

// Priority order for tie-breaking
export const CAREER_PATH_PRIORITY: CareerPathId[] = [
  'quantFinance',
  'softwareEng',
  'aiDataScience',
  'cybersecurity',
  'productUx',
  'techEntrepreneurship'
];
