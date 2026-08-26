import { Question } from '../types';

export const QUESTIONS: Question[] = [
  {
    id: 1,
    stopIndex: 'STOP 01 // 10',
    category: 'PROJECT ARCHITECTURE',
    text: 'You have an open weekend to build a technical project from scratch. Which direction do you take?',
    contextNote: 'Signals core builder orientation and preferred project output.',
    answers: [
      { 
        text: 'A clean web application or game with real-time multiplayer networking',
        code: 'FORK_A',
        weights: { softwareEng: 5, productUx: 3, techEntrepreneurship: 2 } 
      },
      { 
        text: 'A quantitative backtester modeling statistical market pricing and volatility',
        code: 'FORK_B',
        weights: { quantFinance: 5, aiDataScience: 4, softwareEng: 2 } 
      },
      { 
        text: 'A neural classifier trained to detect anomalies or generate structured summaries',
        code: 'FORK_C',
        weights: { aiDataScience: 5, softwareEng: 3, cybersecurity: 2 } 
      },
      { 
        text: 'A vulnerability scanner auditing network services and common protocol weaknesses',
        code: 'FORK_D',
        weights: { cybersecurity: 5, softwareEng: 3, quantFinance: 1 } 
      }
    ]
  },
  {
    id: 2,
    stopIndex: 'STOP 02 // 10',
    category: 'CORE METHODOLOGY',
    text: 'Which academic combination gives you the most satisfaction when working through hard problems?',
    contextNote: 'Identifies foundational cognitive preferences and analytical habits.',
    answers: [
      { 
        text: 'Advanced calculus, probability distributions, and microeconomic models',
        code: 'FORK_A',
        weights: { quantFinance: 5, aiDataScience: 3, techEntrepreneurship: 2 } 
      },
      { 
        text: 'Discrete mathematics, algorithmic complexity, and computer architecture',
        code: 'FORK_B',
        weights: { softwareEng: 5, cybersecurity: 3, aiDataScience: 2 } 
      },
      { 
        text: 'Cognitive psychology, design ergonomics, and visual hierarchy',
        code: 'FORK_C',
        weights: { productUx: 5, techEntrepreneurship: 3, softwareEng: 1 } 
      },
      { 
        text: 'Economics, competitive strategy, and executive debate',
        code: 'FORK_D',
        weights: { techEntrepreneurship: 5, productUx: 3, quantFinance: 2 } 
      }
    ]
  },
  {
    id: 3,
    stopIndex: 'STOP 03 // 10',
    category: 'HANDLING AMBIGUITY',
    text: 'You are handed an ill-defined problem with missing constraints and no spec. What is your first action?',
    contextNote: 'Tests your operating model when confronted with unconstrained uncertainty.',
    answers: [
      { 
        text: 'Define the minimum viable scope, align stakeholders on a shared goal, and build momentum',
        code: 'FORK_A',
        weights: { techEntrepreneurship: 5, productUx: 3, softwareEng: 1 } 
      },
      { 
        text: 'Ingest all available telemetry to uncover underlying statistical correlations and outliers',
        code: 'FORK_B',
        weights: { aiDataScience: 5, quantFinance: 4, cybersecurity: 2 } 
      },
      { 
        text: 'Isolate technical primitives, write an RFC, and construct an incremental proof-of-concept',
        code: 'FORK_C',
        weights: { softwareEng: 5, quantFinance: 3, aiDataScience: 2 } 
      },
      { 
        text: 'Conduct structured interviews with affected users to observe exact friction points first-hand',
        code: 'FORK_D',
        weights: { productUx: 5, techEntrepreneurship: 4, aiDataScience: 1 } 
      }
    ]
  },
  {
    id: 4,
    stopIndex: 'STOP 04 // 10',
    category: 'TEAM DYNAMICS',
    text: 'In a 4-person engineering squad during an intensive hackathon, which responsibility do you gravitate toward?',
    contextNote: 'Reveals your natural team function and operational role.',
    answers: [
      { 
        text: 'Team lead: prioritizing the roadmap, defending the pitch, and coordinating deliverables',
        code: 'FORK_A',
        weights: { techEntrepreneurship: 5, productUx: 2, quantFinance: 1 } 
      },
      { 
        text: 'Core systems engineer: designing database schemas, backend endpoints, and infrastructure',
        code: 'FORK_B',
        weights: { softwareEng: 5, aiDataScience: 2, cybersecurity: 2 } 
      },
      { 
        text: 'Data specialist: building predictive features, statistical pipelines, and analytical evaluations',
        code: 'FORK_C',
        weights: { aiDataScience: 5, quantFinance: 4, softwareEng: 1 } 
      },
      { 
        text: 'Product designer: mapping user flows, Figma mockups, and polishing interface polish',
        code: 'FORK_D',
        weights: { productUx: 5, softwareEng: 2, techEntrepreneurship: 2 } 
      }
    ]
  },
  {
    id: 5,
    stopIndex: 'STOP 05 // 10',
    category: 'ANALYTICAL PUZZLES',
    text: 'What kind of complex investigative puzzle keeps you engaged for hours?',
    contextNote: 'Pinpoints specific problem-solving instincts and curiosity drivers.',
    answers: [
      { 
        text: 'Finding subtle race conditions, memory leaks, and performance bottlenecks in code',
        code: 'FORK_A',
        weights: { softwareEng: 5, cybersecurity: 3, quantFinance: 2 } 
      },
      { 
        text: 'Reverse-engineering a closed protocol to understand edge cases and bypass defenses',
        code: 'FORK_B',
        weights: { cybersecurity: 5, softwareEng: 3, aiDataScience: 1 } 
      },
      { 
        text: 'Identifying statistical arbitrage or predictive drivers in non-stationary datasets',
        code: 'FORK_C',
        weights: { quantFinance: 5, aiDataScience: 4, softwareEng: 1 } 
      },
      { 
        text: 'Diagnosing why users drop off at step 3 of an onboarding funnel and designing a fix',
        code: 'FORK_D',
        weights: { productUx: 5, techEntrepreneurship: 3, aiDataScience: 2 } 
      }
    ]
  },
  {
    id: 6,
    stopIndex: 'STOP 06 // 10',
    category: 'DATA REASONING',
    text: 'You are provided with 500 million transaction log entries. Where do you focus your scrutiny?',
    contextNote: 'Assesses your perspective on large-scale informational assets.',
    answers: [
      { 
        text: 'Evaluating pricing anomalies, volatility clustering, and yield curve anomalies',
        code: 'FORK_A',
        weights: { quantFinance: 5, aiDataScience: 4, softwareEng: 1 } 
      },
      { 
        text: 'Training dimensionality-reduction and clustering models to segment behavioral cohorts',
        code: 'FORK_B',
        weights: { aiDataScience: 5, quantFinance: 3, softwareEng: 2 } 
      },
      { 
        text: 'Auditing authentication traces for credential stuffing and unauthorized lateral movement',
        code: 'FORK_C',
        weights: { cybersecurity: 5, softwareEng: 3, quantFinance: 1 } 
      },
      { 
        text: 'Benchmarking query latency, partition pruning, and cache hit rates in the datastore',
        code: 'FORK_D',
        weights: { softwareEng: 5, cybersecurity: 2, quantFinance: 2 } 
      }
    ]
  },
  {
    id: 7,
    stopIndex: 'STOP 07 // 10',
    category: 'TECHNICAL PUBLISHING',
    text: 'If you were to publish a deep-dive technical engineering article, what would the subject matter be?',
    contextNote: 'Indicates authentic knowledge interests and technical taste.',
    answers: [
      { 
        text: 'Architecting high-concurrency event loops and zero-copy networking in Rust',
        code: 'FORK_A',
        weights: { softwareEng: 5, cybersecurity: 2, quantFinance: 2 } 
      },
      { 
        text: 'Mathematical proofs and implementation of Black-Scholes versus jump-diffusion pricing models',
        code: 'FORK_B',
        weights: { quantFinance: 5, aiDataScience: 3, techEntrepreneurship: 1 } 
      },
      { 
        text: 'A critique of micro-interaction patterns in developer tools and accessibility standards',
        code: 'FORK_C',
        weights: { productUx: 5, techEntrepreneurship: 2, softwareEng: 2 } 
      },
      { 
        text: 'Dissecting a kernel zero-day exploit and modern memory-safety mitigation techniques',
        code: 'FORK_D',
        weights: { cybersecurity: 5, softwareEng: 3, quantFinance: 1 } 
      }
    ]
  },
  {
    id: 8,
    stopIndex: 'STOP 08 // 10',
    category: 'FUTURE INFRASTRUCTURE',
    text: 'Which technological paradigm shift represents the most critical engineering frontier over the next decade?',
    contextNote: 'Surveys forward-looking technical vision and strategic horizon.',
    answers: [
      { 
        text: 'Self-improving neural models that synthesize verified formal logic and code',
        code: 'FORK_A',
        weights: { aiDataScience: 5, softwareEng: 3, quantFinance: 2 } 
      },
      { 
        text: 'Pioneering vertical market software that digitizes legacy manual industries from the ground up',
        code: 'FORK_B',
        weights: { techEntrepreneurship: 5, productUx: 3, quantFinance: 2 } 
      },
      { 
        text: 'Spatial computing and frictionless interfaces that eliminate cognitive load for operators',
        code: 'FORK_C',
        weights: { productUx: 5, softwareEng: 3, techEntrepreneurship: 2 } 
      },
      { 
        text: 'Post-quantum cryptography and zero-trust verification across global critical infrastructure',
        code: 'FORK_D',
        weights: { cybersecurity: 5, softwareEng: 3, quantFinance: 1 } 
      }
    ]
  },
  {
    id: 9,
    stopIndex: 'STOP 09 // 10',
    category: 'CONFERENCE WORKSHOPS',
    text: 'You attend a major technical conference with limited time. Which hands-on workshop do you attend?',
    contextNote: 'Checks your instinct for hands-on skill acquisition.',
    answers: [
      { 
        text: 'Building a distributed key-value store with Raft consensus from scratch',
        code: 'FORK_A',
        weights: { softwareEng: 5, cybersecurity: 2, aiDataScience: 2 } 
      },
      { 
        text: 'Constructing early-stage venture pitch decks and navigating customer acquisition unit economics',
        code: 'FORK_B',
        weights: { techEntrepreneurship: 5, productUx: 3, quantFinance: 2 } 
      },
      { 
        text: 'Live exploitation lab: reverse engineering binaries and auditing modern cryptographic protocols',
        code: 'FORK_C',
        weights: { cybersecurity: 5, softwareEng: 3, aiDataScience: 1 } 
      },
      { 
        text: 'Conducting guerrilla usability tests, Figma design tokens, and systematic design system audits',
        code: 'FORK_D',
        weights: { productUx: 5, techEntrepreneurship: 2, softwareEng: 2 } 
      }
    ]
  },
  {
    id: 10,
    stopIndex: 'STOP 10 // 10',
    category: 'LONG-TERM AMBITION',
    text: 'Looking ahead 5 years, what role best reflects your ideal day-to-day contribution?',
    contextNote: 'Determines overall destination alignment and career vision.',
    answers: [
      { 
        text: 'Staff Software Architect leading technical roadmaps and authoring mission-critical services',
        code: 'FORK_A',
        weights: { softwareEng: 5, productUx: 2, techEntrepreneurship: 2 } 
      },
      { 
        text: 'Head of Product defining user journeys, feature requirements, and high-fidelity specifications',
        code: 'FORK_B',
        weights: { productUx: 5, techEntrepreneurship: 3, softwareEng: 2 } 
      },
      { 
        text: 'Quantitative Portfolio Strategist developing predictive models and high-throughput trade logic',
        code: 'FORK_C',
        weights: { quantFinance: 5, aiDataScience: 4, softwareEng: 1 } 
      },
      { 
        text: 'Lead Security Researcher uncovering zero-day vulnerabilities and fortifying defensive postures',
        code: 'FORK_D',
        weights: { cybersecurity: 5, softwareEng: 3, quantFinance: 1 } 
      }
    ]
  }
];
