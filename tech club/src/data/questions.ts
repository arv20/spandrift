import { Question } from '../types';

export const QUESTIONS: Question[] = [
  {
    id: 1,
    text: "You have a free weekend to build something. What sounds most exciting?",
    answers: [
      { text: "A web app or game for my friends to play", weights: { softwareEng: 5, productUx: 3, techEntrepreneurship: 2 } },
      { text: "A tool that predicts sports outcomes based on stats", weights: { quantFinance: 5, aiDataScience: 4, softwareEng: 2 } },
      { text: "A sleek, beautiful portfolio to show off my ideas", weights: { productUx: 5, techEntrepreneurship: 3, softwareEng: 1 } },
      { text: "A script that automates a boring task", weights: { cybersecurity: 4, aiDataScience: 3, softwareEng: 4 } }
    ]
  },
  {
    id: 2,
    text: "When it comes to your favorite subjects in school, which combination clicks best with you?",
    answers: [
      { text: "Math, Statistics, and Economics", weights: { quantFinance: 5, aiDataScience: 3, techEntrepreneurship: 1 } },
      { text: "Computer Science and Logic", weights: { softwareEng: 5, cybersecurity: 3, aiDataScience: 2 } },
      { text: "Art, Psychology, and Design", weights: { productUx: 5, techEntrepreneurship: 2, softwareEng: 1 } },
      { text: "Business, Debate, and Leadership", weights: { techEntrepreneurship: 5, productUx: 3, quantFinance: 2 } }
    ]
  },
  {
    id: 3,
    text: "You're given a messy, ambiguous problem with no clear instructions. What's your first move?",
    answers: [
      { text: "Gather the team and brainstorm a vision", weights: { techEntrepreneurship: 5, productUx: 3, softwareEng: 1 } },
      { text: "Look for patterns and hidden clues in the data", weights: { aiDataScience: 5, quantFinance: 4, cybersecurity: 3 } },
      { text: "Break it down into smaller, logical steps", weights: { softwareEng: 5, quantFinance: 3, aiDataScience: 2 } },
      { text: "Interview people who are affected by the problem", weights: { productUx: 5, techEntrepreneurship: 4, aiDataScience: 1 } }
    ]
  },
  {
    id: 4,
    text: "On a group project, what role do you naturally fall into?",
    answers: [
      { text: "The leader who organizes and pitches the final idea", weights: { techEntrepreneurship: 5, productUx: 2, quantFinance: 1 } },
      { text: "The builder who actually puts the pieces together", weights: { softwareEng: 5, aiDataScience: 2, cybersecurity: 1 } },
      { text: "The researcher analyzing all the facts and figures", weights: { aiDataScience: 5, quantFinance: 5, cybersecurity: 2 } },
      { text: "The designer making sure the final product looks perfect", weights: { productUx: 5, softwareEng: 2, techEntrepreneurship: 2 } }
    ]
  },
  {
    id: 5,
    text: "What kind of puzzle or challenge appeals to you the most?",
    answers: [
      { text: "Finding the fastest, most efficient way to solve a maze", weights: { softwareEng: 5, quantFinance: 3, aiDataScience: 2 } },
      { text: "Figuring out how a magic trick works behind the scenes", weights: { cybersecurity: 5, softwareEng: 3, aiDataScience: 2 } },
      { text: "Predicting what someone will do before they do it", weights: { aiDataScience: 5, quantFinance: 4, productUx: 2 } },
      { text: "Finding the loopholes in a set of complex rules", weights: { cybersecurity: 5, quantFinance: 3, techEntrepreneurship: 3 } }
    ]
  },
  {
    id: 6,
    text: "You are handed a massive spreadsheet with one million rows of data. What's your reaction?",
    answers: [
      { text: "Write a script to visualize it and find trends", weights: { aiDataScience: 5, quantFinance: 4, softwareEng: 2 } },
      { text: "Analyze it for potential profit opportunities", weights: { quantFinance: 5, techEntrepreneurship: 3, aiDataScience: 3 } },
      { text: "Figure out how to compress and store it safely", weights: { cybersecurity: 5, softwareEng: 4, aiDataScience: 1 } },
      { text: "Use it to understand what users want", weights: { productUx: 5, techEntrepreneurship: 4, aiDataScience: 2 } }
    ]
  },
  {
    id: 7,
    text: "If you were to create content online, what would it be?",
    answers: [
      { text: "Tutorials on how to code or build apps", weights: { softwareEng: 5, aiDataScience: 2, techEntrepreneurship: 1 } },
      { text: "Deep dives into market trends and investing", weights: { quantFinance: 5, techEntrepreneurship: 3, aiDataScience: 1 } },
      { text: "Reviews of well-designed products and apps", weights: { productUx: 5, techEntrepreneurship: 2, softwareEng: 2 } },
      { text: "Exposing scams and teaching digital safety", weights: { cybersecurity: 5, softwareEng: 2, aiDataScience: 1 } }
    ]
  },
  {
    id: 8,
    text: "What excites you the most about the future of technology?",
    answers: [
      { text: "Machines that can think and learn like humans", weights: { aiDataScience: 5, softwareEng: 3, quantFinance: 2 } },
      { text: "Building entirely new industries and businesses", weights: { techEntrepreneurship: 5, productUx: 3, quantFinance: 2 } },
      { text: "Seamless apps that make everyday life effortless", weights: { productUx: 5, softwareEng: 4, techEntrepreneurship: 2 } },
      { text: "Advanced cryptography to protect privacy", weights: { cybersecurity: 5, softwareEng: 3, quantFinance: 1 } }
    ]
  },
  {
    id: 9,
    text: "How would you spend your time at a massive tech conference?",
    answers: [
      { text: "Attending a hackathon to build something in 24 hours", weights: { softwareEng: 5, techEntrepreneurship: 3, aiDataScience: 2 } },
      { text: "Networking with investors and pitching ideas", weights: { techEntrepreneurship: 5, quantFinance: 3, productUx: 2 } },
      { text: "Learning about the latest vulnerabilities and exploits", weights: { cybersecurity: 5, softwareEng: 3, aiDataScience: 1 } },
      { text: "Checking out the most beautiful new hardware and software", weights: { productUx: 5, techEntrepreneurship: 2, softwareEng: 2 } }
    ]
  },
  {
    id: 10,
    text: "Imagine your dream first job in tech. What does it look like?",
    answers: [
      { text: "Writing code that millions of people use daily", weights: { softwareEng: 5, productUx: 3, techEntrepreneurship: 1 } },
      { text: "Designing the look and feel of a popular new app", weights: { productUx: 5, techEntrepreneurship: 2, softwareEng: 2 } },
      { text: "Analyzing algorithms for a top trading firm", weights: { quantFinance: 5, aiDataScience: 3, softwareEng: 2 } },
      { text: "Securing a major company's servers from hackers", weights: { cybersecurity: 5, softwareEng: 3, aiDataScience: 2 } }
    ]
  }
];
