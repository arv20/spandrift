# Find Your Tech Path

> A 60-second career quiz by Dublin Tech Club to help high school students explore technology career paths.

**Find Your Tech Path** is a lightweight, responsive, and interactive static quiz website designed to help high school students discover technology fields aligned with their natural interests and strengths.

Built with **React**, **TypeScript**, and **Vite**, and designed for seamless zero-config deployment via **GitHub Pages**.

> [!NOTE]
> **Disclaimer:** This quiz is an exploration tool designed to inspire curiosity and introduce potential career pathways, not a formal or scientific assessment.

---

## Features

- ⚡ **Fast & Lightweight:** 60-second quiz experience with instant scoring.
- 🎯 **Multi-Weighted Scoring:** Answers distribute points across multiple tech paths with deterministic tie-breaking.
- 📱 **Fully Responsive & Accessible:** Optimized for mobile, tablet, and desktop viewports with ARIA support and reduced motion preferences.
- 🎨 **Modular Styling:** Built using CSS Modules and CSS custom properties.
- 🚀 **GitHub Pages Ready:** Automated CI/CD workflow with GitHub Actions.

---

## Quick Start (Local Development)

### Prerequisites
- Node.js 20+
- npm

### Installation & Run

```bash
# Clone the repository
git clone <repo-url>

# Navigate into project directory
cd find-your-tech-path

# Install dependencies
npm install

# Start local development server
npm run dev
```

---

## Running Tests

The project uses [Vitest](https://vitest.dev/) and [@testing-library/react](https://testing-library.com/docs/react-testing-library/intro/) for unit and integration testing.

```bash
# Run test suite once
npm test

# Run tests in interactive watch mode
npm run test:watch
```

---

## Production Build

```bash
# Type check and build optimized bundle for production
npm run build

# Preview the production build locally
npm run preview
```

---

## Deploying to GitHub Pages

1. **Fork or create the repository** on GitHub.
2. **Update Base Path:**
   Update the `base` path in `vite.config.ts` (or set the `VITE_BASE_PATH` environment variable) to match your repository name.
   - For example, if your repo is `my-org/tech-quiz`, set `base: '/tech-quiz/'`.
   - The default configuration is `'/find-your-tech-path/'`.
3. **Configure Pages Settings:**
   - In your GitHub repository, go to **Settings** → **Pages**.
   - Under **Build and deployment** > **Source**, select **GitHub Actions**.
4. **Deploy:**
   - Push your changes to the `main` branch.
   - The included GitHub Actions workflow (`.github/workflows/deploy.yml`) will automatically run tests, build the application, and publish to GitHub Pages.
5. **Visit Your Site:**
   - Your site will be live at `https://<username>.github.io/<repo-name>/`.

---

## Customizing for Your Club

### Updating Club Information

Edit the placeholder values in [`src/screens/ResultsScreen.tsx`](src/screens/ResultsScreen.tsx):

- `[JOIN LINK]` — Link to your club registration/signup form.
- `[INSTAGRAM HANDLE]` — Your club's Instagram username or social link.
- `[MEETING INFORMATION]` — When and where your club meets (e.g. room number, day, and time).
- `[QR CODE]` — Replace with your actual club link QR code image asset.

---

## Editing Quiz Content

### Questions and Scoring (`src/data/questions.ts`)

- Each question features 4 distinct answer choices.
- Each choice awards weighted points (1–5) across multiple career paths.
- Weights represent the strength of correlation between that answer and a tech path.
- Every answer should contribute points to at least 2–3 career paths to ensure balanced scoring.

### Career Path Results (`src/data/careerPaths.ts`)

- Customize path descriptions, core tools, key skills, and starter projects.
- Accent colors, theme variables, and emoji icons can be tailored per path.
- The `CAREER_PATH_PRIORITY` array defines the deterministic tie-breaking order when two paths finish with equal scores.

### LARP Mode Copy (`src/data/larpCopy.ts`)

- Fun alternative copy for the UI easter egg mode.
- Purely cosmetic flavor text that does not alter underlying quiz scoring mechanics.

---

## Project Structure

```
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions CI/CD deployment workflow
├── public/                     # Static assets and favicons
├── src/
│   ├── components/             # Shared UI components (Button, ProgressBar, Layout, etc.)
│   ├── data/                   # Questions, career paths, and copy definitions
│   ├── scoring/                # Pure scoring engine and tie-breaking algorithms
│   ├── screens/                # Landing, Question, and Results views
│   ├── state/                  # React context and quiz state management
│   ├── styles/                 # CSS variables, typography, and global styles
│   ├── App.tsx                 # Root application component
│   └── main.tsx                # Application entry point
├── LICENSE                     # MIT License
├── package.json                # Project dependencies and npm scripts
├── tsconfig.json               # TypeScript configuration
└── vite.config.ts              # Vite bundler configuration
```

---

## License

This project is licensed under the [MIT License](LICENSE) — see the [LICENSE](LICENSE) file for details.
