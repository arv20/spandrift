import { CareerPath, CareerPathId } from '../types';

export const CAREER_PATHS: CareerPath[] = [
  {
    id: 'quantFinance',
    code: 'ROUTE_QUANT',
    name: 'Quantitative Finance & Algorithmic Trading',
    badge: 'QUANT-FIN',
    accentColor: '#3EA39E', // --route
    tagline: 'Model stochastic systems, pricing dynamics, and high-throughput market data.',
    description: 'Quantitative engineers and researchers apply advanced statistics, time-series forecasting, and low-latency programming to find signal in financial markets.',
    whyItFits: 'Your answers prioritize rigorous mathematical modeling, empirical verification, and extracting structured patterns from noisy real-world data.',
    typicalProblems: [
      'Backtesting algorithmic trading strategies against historical order-book feeds',
      'Optimizing portfolio risk and asset allocations using stochastic calculus',
      'Minimizing trade execution latency on high-frequency market interfaces',
      'Detecting anomalies and regime shifts in macroeconomic time-series'
    ],
    skills: ['Linear Algebra & Multivariable Calculus', 'Probability & Statistics', 'Time Series Modeling', 'C++ / Python', 'Market Mechanics'],
    tools: ['Python (NumPy / Pandas)', 'Jupyter Lab', 'C++ / Rust'],
    starterProject: 'Build a historical backtester that executes simple moving-average crossovers on Yahoo Finance data with slippage simulation.',
    clubTrack: 'Dublin Tech Club Quantitative Modeling Group & Algorithmic Hackathon Track'
  },
  {
    id: 'softwareEng',
    code: 'ROUTE_SWE',
    name: 'Systems & Software Engineering',
    badge: 'SYS-ENG',
    accentColor: '#E8A33D', // --signal
    tagline: 'Architect robust distributed software, developer tooling, and scalable applications.',
    description: 'Software engineers design, implement, and maintain reliable software architectures — from backend microservices and databases to high-performance client runtimes.',
    whyItFits: 'Your choices emphasize logical decomposition, building tangible tools from scratch, and solving architectural puzzles through clean, maintainable code.',
    typicalProblems: [
      'Decomposing complex business workflows into decoupled service endpoints',
      'Designing concurrent database schemas and caching layers for sub-10ms response times',
      'Troubleshooting race conditions, memory leaks, and distributed deadlocks',
      'Establishing automated CI/CD deployment pipelines and comprehensive regression suites'
    ],
    skills: ['Data Structures & Algorithms', 'System Architecture', 'Version Control (Git)', 'API Design (REST / gRPC)', 'Database Indexing'],
    tools: ['TypeScript / Node.js', 'Go or Rust', 'PostgreSQL'],
    starterProject: 'Build a lightweight CLI tool or real-time collaborative workspace using WebSockets and an SQLite database.',
    clubTrack: 'Dublin Tech Club Open-Source Incubator & Annual 24h Hackathon Team'
  },
  {
    id: 'aiDataScience',
    code: 'ROUTE_AI_DATA',
    name: 'Applied Machine Learning & Data Science',
    badge: 'ML-DATA',
    accentColor: '#3EA39E', // --route
    tagline: 'Train neural architectures, evaluate statistical models, and transform raw data into intelligence.',
    description: 'ML engineers and data scientists build systems that generalize from large datasets — training predictive models, fine-tuning neural networks, and automating analytical decisions.',
    whyItFits: 'You consistently leaned toward experimentation, statistical inference, and training computer systems to recognize complex multidimensional patterns.',
    typicalProblems: [
      'Cleaning, normalizing, and feature-engineering high-cardinality real-world data',
      'Fine-tuning transformer language models or vision encoders for domain-specific tasks',
      'Evaluating model hallucination, calibration error, and bias metrics across validation splits',
      'Deploying low-latency model inference pipelines with batching and GPU acceleration'
    ],
    skills: ['Applied Statistics & Matrix Algebra', 'Supervised / Unsupervised Learning', 'Model Evaluation & Loss Functions', 'Data Wrangling', 'Python'],
    tools: ['PyTorch / Scikit-Learn', 'Pandas & DuckDB', 'Weights & Biases'],
    starterProject: 'Train and evaluate a classifier on a Kaggle dataset (e.g. text sentiment or sensor telemetry), measuring Precision, Recall, and ROC-AUC curves.',
    clubTrack: 'Dublin Tech Club AI Research Group & Applied Kaggle Competition Cohort'
  },
  {
    id: 'cybersecurity',
    code: 'ROUTE_SECURITY',
    name: 'Cybersecurity & Defensive Engineering',
    badge: 'SEC-DEF',
    accentColor: '#E8A33D', // --signal
    tagline: 'Audit system vulnerabilities, reverse-engineer binaries, and fortify critical infrastructure.',
    description: 'Security engineers analyze software, networks, and protocols from an adversarial perspective to discover vulnerabilities before malicious actors can exploit them.',
    whyItFits: 'Your answers reflect an investigative instinct: dissecting complex rule sets, anticipating edge-case exploits, and protecting systems against failure modes.',
    typicalProblems: [
      'Auditing application code for injection flaws, authentication bypasses, and CSRF vulnerabilities',
      'Configuring network segmentation, zero-trust policies, and cryptographic key rotation',
      'Analyzing suspicious packet captures (PCAP) and reverse-engineering obfuscated binaries',
      'Drafting threat models and incident response runbooks for production services'
    ],
    skills: ['Computer Networking (TCP/IP & DNS)', 'Cryptography Fundamentals', 'Linux Internals & Bash', 'Threat Modeling', 'Web Application Security'],
    tools: ['Wireshark', 'Burp Suite', 'GDB / Ghidra'],
    starterProject: 'Build an automated TLS configuration checker and security-header auditor in Python that grades any public URL.',
    clubTrack: 'Dublin Tech Club Capture The Flag (CTF) Team & Hands-On Cyber Defense Labs'
  },
  {
    id: 'productUx',
    code: 'ROUTE_PRODUCT_UX',
    name: 'Product Architecture & Interaction Design',
    badge: 'PROD-UX',
    accentColor: '#3EA39E', // --route
    tagline: 'Synthesize user needs, design ergonomic workflows, and turn ambiguity into clear roadmaps.',
    description: 'Product managers and UX architects bridge technical feasibility with human psychology — mapping user journeys, constructing clickable prototypes, and validating solutions.',
    whyItFits: 'You prioritize usability, structured user interviews, ergonomics, and translating fuzzy problems into coherent, elegant product specifications.',
    typicalProblems: [
      'Identifying core user friction points through structured observational testing',
      'Mapping complex multi-step workflows into minimal-friction wireframes and interactive prototypes',
      'Defining quantitative success metrics (activation, retention, completion rates) for feature releases',
      'Balancing engineering scope constraints against user requirements to ship timely MVPs'
    ],
    skills: ['Information Architecture', 'Usability Testing', 'Interactive Prototyping', 'Design Systems', 'Technical Spec Writing'],
    tools: ['Figma', 'Linear / Notion', 'Lookback / UserTesting'],
    starterProject: 'Conduct 5 user interviews on a frustrating school software tool, produce an improved user-flow diagram, and build a high-fidelity Figma prototype.',
    clubTrack: 'Dublin Tech Club Design Systems Workshop & Product Pitch Competitions'
  },
  {
    id: 'techEntrepreneurship',
    code: 'ROUTE_FOUNDER',
    name: 'Technical Entrepreneurship & Venture Building',
    badge: 'ENT-VENTURE',
    accentColor: '#E8A33D', // --signal
    tagline: 'Formulate venture theses, assemble engineering teams, and ship products that solve market needs.',
    description: 'Technical founders discover high-value problems, recruit co-founders, secure initial traction, and scale technology products from zero to viable operating organizations.',
    whyItFits: 'Your answers indicate a strong bias for agency: rallying teammates around a shared thesis, making high-stakes trade-offs under uncertainty, and driving products to market.',
    typicalProblems: [
      'Conducting customer discovery interviews to validate willingness-to-pay before writing code',
      'Pitching technical architecture and market opportunity to early advisors and grant committees',
      'Scoping an initial Minimum Viable Product (MVP) that can be built and launched in 3 weeks',
      'Managing cash burn, product roadmap velocity, and cross-functional team execution'
    ],
    skills: ['Customer Discovery', 'Venture Economics & Unit Economics', 'Executive Communication', 'Agile Product Delivery', 'Strategic Prioritization'],
    tools: ['Business Model Canvas', 'Notion', 'Pitch Decks (Keynote/Figma)'],
    starterProject: 'Write a 2-page product requirement document (PRD) for a micro-SaaS targeting student clubs, validate it with 10 club leaders, and build a landing page with pre-orders.',
    clubTrack: 'Dublin Tech Club Founder Cohort & High School Startup Pitch Showcase'
  }
];

export const CAREER_PATH_MAP: Record<CareerPathId, CareerPath> = CAREER_PATHS.reduce((acc, path) => {
  acc[path.id] = path;
  return acc;
}, {} as Record<CareerPathId, CareerPath>);

// Priority order for deterministic tie-breaking
export const CAREER_PATH_PRIORITY: CareerPathId[] = [
  'quantFinance',
  'softwareEng',
  'aiDataScience',
  'cybersecurity',
  'productUx',
  'techEntrepreneurship'
];
