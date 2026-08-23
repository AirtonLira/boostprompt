# BoostPrompt Immersive Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static, accessible and immersive landing page that explains BoostPrompt and deploys automatically to GitHub Pages.

**Architecture:** The new `site/` workspace is an Astro static site, separate from the Python package. Astro renders all essential copy; client islands load the R3F scene only when the device can support it, while GSAP is dynamically imported only for desktop scroll choreography. GitHub Actions builds `site/dist` and deploys it as the Pages artifact.

**Tech Stack:** Astro 7.2, React 19, TypeScript, React Three Fiber, Three.js, GSAP, Vitest, GitHub Actions, GitHub Pages.

---

## File Structure

```text
site/
├── package.json                         # scripts and frontend dependencies
├── astro.config.mjs                     # Astro Pages base and React integration
├── tsconfig.json                        # strict TypeScript configuration
├── public/favicon.svg                   # logo-derived browser icon
├── scripts/verify-build.mjs             # verifies built CTA and product copy
└── src/
    ├── data/product.ts                  # one source of product facts and URLs
    ├── data/product.test.ts              # content contract
    ├── lib/experience.ts                 # pure motion/scene eligibility rules
    ├── lib/experience.test.ts            # reduced-motion and viewport contract
    ├── layouts/BaseLayout.astro          # document metadata and global CSS
    ├── pages/index.astro                 # landing page composition
    ├── components/Header.astro           # accessible fixed navigation
    ├── components/HeroSection.astro      # value proposition and scene fallback
    ├── components/ScrollNarrative.astro  # semantic three-stage story
    ├── components/FeatureGrid.astro      # product differentials
    ├── components/FinalCta.astro         # GitHub conversion section
    ├── components/PromptScene.tsx        # client-only R3F scene shell
    ├── components/PromptCanvas.tsx       # lazily imported WebGL geometry
    ├── scripts/scrollNarrative.ts        # lazily imported GSAP lifecycle
    └── styles/global.css                 # responsive visual system and fallback
.github/workflows/deploy-pages.yml        # Pages build and deployment
```

### Task 1: Bootstrap the isolated Astro workspace

**Files:**
- Create: `site/package.json`
- Create: `site/astro.config.mjs`
- Create: `site/tsconfig.json`
- Create: `site/src/env.d.ts`
- Create: `site/public/favicon.svg`

- [ ] **Step 1: Define the frontend package and deployment base configuration**

```json
{
  "name": "boostprompt-site",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "test": "vitest run",
    "check": "astro check",
    "verify:build": "node scripts/verify-build.mjs"
  },
  "dependencies": {
    "@astrojs/react": "^6.0.4",
    "@react-three/drei": "^10.7.8",
    "@react-three/fiber": "^9.7.0",
    "astro": "^7.2.4",
    "gsap": "^3.15.0",
    "react": "^19.2.8",
    "react-dom": "^19.2.8",
    "three": "^0.185.1"
  },
  "devDependencies": {
    "@astrojs/check": "^0.9.10",
    "@types/node": "^24.0.0",
    "@types/react": "^19.2.0",
    "@types/react-dom": "^19.2.0",
    "typescript": "^6.0.3",
    "vitest": "^4.1.11"
  }
}
```

```js
// site/astro.config.mjs
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

const isPagesBuild = process.env.GITHUB_ACTIONS === 'true';

export default defineConfig({
  site: isPagesBuild ? 'https://airtonlira.github.io' : 'http://localhost:4321',
  base: isPagesBuild ? '/boostprompt' : '/',
  integrations: [react()],
});
```

- [ ] **Step 2: Install dependencies and confirm Astro starts from `site/`**

Run: `npm install && npm run check` from `site/`

Expected: dependencies resolve and `astro check` exits 0 once the minimal `src/env.d.ts` contains `/// <reference types="astro/client" />`.

- [ ] **Step 3: Commit the frontend toolchain**

```bash
git add site/package.json site/package-lock.json site/astro.config.mjs site/tsconfig.json site/src/env.d.ts site/public/favicon.svg
git commit -m "chore: bootstrap BoostPrompt site"
```

### Task 2: Establish verified product copy and motion rules with tests

**Files:**
- Create: `site/src/data/product.test.ts`
- Create: `site/src/data/product.ts`
- Create: `site/src/lib/experience.test.ts`
- Create: `site/src/lib/experience.ts`

- [ ] **Step 1: Write failing contracts for the public facts and GitHub CTA**

```ts
// site/src/data/product.test.ts
import { describe, expect, it } from 'vitest';
import { product } from './product';

describe('product landing content', () => {
  it('links the primary CTA to the canonical repository', () => {
    expect(product.repositoryUrl).toBe('https://github.com/AirtonLira/boostprompt');
  });

  it('contains the documented discovery, research and delivery differentiators', () => {
    expect(product.features.map(({ id }) => id)).toEqual(
      expect.arrayContaining(['adaptive-discovery', 'auditable-research', 'validated-delivery']),
    );
    expect(product.questionRange).toEqual([30, 50]);
  });
});
```

- [ ] **Step 2: Run the content contract and confirm it fails because `./product` does not exist**

Run: `npm test -- src/data/product.test.ts`

Expected: FAIL with a module-resolution error for `./product`.

- [ ] **Step 3: Write the minimal product data module**

```ts
export const product = {
  name: 'BoostPrompt',
  repositoryUrl: 'https://github.com/AirtonLira/boostprompt',
  questionRange: [30, 50] as const,
  features: [
    { id: 'adaptive-discovery', title: 'Discovery adaptativo', detail: 'Perguntas, alternativas e trade-offs em contexto.' },
    { id: 'auditable-research', title: 'Pesquisa auditável', detail: 'Fontes preservadas quando uma decisão externa precisa de evidência.' },
    { id: 'validated-delivery', title: 'Entrega validada', detail: 'Prompt mestre com requisitos, critérios de aceite e plano.' },
    { id: 'continuity', title: 'Memória e retomada', detail: 'Sessões persistidas, resumo estruturado e continuação de entrevistas.' },
    { id: 'quality', title: 'Qualidade observável', detail: 'Cobertura, clareza de decisões e prontidão do prompt.' },
    { id: 'harnesses', title: 'Pronto para o seu harness', detail: 'CLI/TUI local e skills para Claude Code e Codex.' },
  ],
} as const;
```

- [ ] **Step 4: Run the content contract and confirm it passes**

Run: `npm test -- src/data/product.test.ts`

Expected: PASS with 2 tests.

- [ ] **Step 5: Write the failing eligibility contract for reduced motion and mobile**

```ts
// site/src/lib/experience.test.ts
import { describe, expect, it } from 'vitest';
import { shouldUseInteractiveScene, shouldUseScrollSequence } from './experience';

describe('experience eligibility', () => {
  it('keeps the 3D scene disabled for reduced motion, coarse pointers and narrow screens', () => {
    expect(shouldUseInteractiveScene({ reducedMotion: true, finePointer: true, wideViewport: true })).toBe(false);
    expect(shouldUseInteractiveScene({ reducedMotion: false, finePointer: false, wideViewport: true })).toBe(false);
    expect(shouldUseInteractiveScene({ reducedMotion: false, finePointer: true, wideViewport: false })).toBe(false);
    expect(shouldUseInteractiveScene({ reducedMotion: false, finePointer: true, wideViewport: true })).toBe(true);
  });

  it('enables scroll choreography only on a motion-safe desktop viewport', () => {
    expect(shouldUseScrollSequence({ reducedMotion: false, wideViewport: true })).toBe(true);
    expect(shouldUseScrollSequence({ reducedMotion: true, wideViewport: true })).toBe(false);
  });
});
```

- [ ] **Step 6: Run the experience contract and confirm it fails because `./experience` does not exist**

Run: `npm test -- src/lib/experience.test.ts`

Expected: FAIL with a module-resolution error for `./experience`.

- [ ] **Step 7: Implement the pure eligibility helpers**

```ts
export type SceneEnvironment = { reducedMotion: boolean; finePointer: boolean; wideViewport: boolean };
export type ScrollEnvironment = Pick<SceneEnvironment, 'reducedMotion' | 'wideViewport'>;

export const shouldUseInteractiveScene = ({ reducedMotion, finePointer, wideViewport }: SceneEnvironment) =>
  !reducedMotion && finePointer && wideViewport;

export const shouldUseScrollSequence = ({ reducedMotion, wideViewport }: ScrollEnvironment) =>
  !reducedMotion && wideViewport;
```

- [ ] **Step 8: Run all frontend unit tests and commit the contracts**

Run: `npm test`

Expected: PASS with 4 tests.

```bash
git add site/src/data site/src/lib
git commit -m "feat: define landing content and motion rules"
```

### Task 3: Build the accessible Astro page and static fallback

**Files:**
- Create: `site/src/layouts/BaseLayout.astro`
- Create: `site/src/components/Header.astro`
- Create: `site/src/components/HeroSection.astro`
- Create: `site/src/components/ScrollNarrative.astro`
- Create: `site/src/components/FeatureGrid.astro`
- Create: `site/src/components/FinalCta.astro`
- Create: `site/src/pages/index.astro`
- Create: `site/src/styles/global.css`
- Create: `site/scripts/verify-build.mjs`

- [ ] **Step 1: Write a failing output verifier before composing the page**

```js
// site/scripts/verify-build.mjs
import { readFile } from 'node:fs/promises';

const html = await readFile(new URL('../dist/index.html', import.meta.url), 'utf8');
const required = [
  'Descubra antes. Construa certo.',
  'Discovery adaptativo',
  'Pesquisa auditável',
  'Prompt mestre',
  'data-scene-fallback',
  'https://github.com/AirtonLira/boostprompt',
];

for (const fragment of required) {
  if (!html.includes(fragment)) throw new Error(`Missing landing fragment: ${fragment}`);
}
```

- [ ] **Step 2: Run the verifier and confirm it fails before `dist/index.html` exists**

Run: `node scripts/verify-build.mjs`

Expected: FAIL with `ENOENT` for `dist/index.html`.

- [ ] **Step 3: Implement the server-rendered layout and sections**

The page must use semantic `header`, `main`, `section`, `article`, `nav` and `footer` elements. `index.astro` imports the layout and sections in this order: `Header`, `HeroSection`, `ScrollNarrative`, `FeatureGrid`, `FinalCta`. `HeroSection` always renders the copy and an `aria-hidden="true"` static speech-bubble/lightning fallback. `FeatureGrid` maps `product.features`; `FinalCta` receives `product.repositoryUrl` and renders a normal external anchor with `target="_blank"` and `rel="noreferrer"`.

`BaseLayout.astro` sets the Portuguese language, concise title/description, favicon and imports `global.css`. `global.css` implements the logo palette (`#050816`, `#F7F9FF`, `#45E3EE`, `#168AFF`, `#8451FF`), the responsive non-centered hero, focus outlines, media queries below 768px, and the `prefers-reduced-motion` override that disables all transitions and presents the narrative linearly.

- [ ] **Step 4: Build and run the static output verifier**

Run: `npm run build && npm run verify:build`

Expected: Astro writes `dist/index.html`; verifier exits 0.

- [ ] **Step 5: Commit the static accessible landing**

```bash
git add site/src/layouts site/src/components site/src/pages site/src/styles site/scripts
git commit -m "feat: add accessible BoostPrompt landing"
```

### Task 4: Add isolated 3D and scroll interactions

**Files:**
- Create: `site/src/components/PromptScene.tsx`
- Create: `site/src/components/PromptCanvas.tsx`
- Create: `site/src/scripts/scrollNarrative.ts`
- Modify: `site/src/components/HeroSection.astro`
- Modify: `site/src/components/ScrollNarrative.astro`
- Modify: `site/src/styles/global.css`

- [ ] **Step 1: Write a failing test that browser media results become the scene environment**

```ts
// append to site/src/lib/experience.test.ts
import { browserSceneEnvironment } from './experience';

it('maps browser media results to the 3D eligibility environment', () => {
  const matches = (query: string) => query !== '(prefers-reduced-motion: reduce)';
  expect(browserSceneEnvironment(matches)).toEqual({
    reducedMotion: false,
    finePointer: true,
    wideViewport: true,
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails because `browserSceneEnvironment` does not exist**

Run: `npm test -- src/lib/experience.test.ts`

Expected: FAIL with an import error for `browserSceneEnvironment`.

- [ ] **Step 3: Implement a lazily loaded scene shell and decorative canvas**

First add this helper to `experience.ts`, then have `PromptScene.tsx` pass `browserSceneEnvironment((query) => window.matchMedia(query).matches)` to `shouldUseInteractiveScene`:

```ts
export const browserSceneEnvironment = (matches: (query: string) => boolean): SceneEnvironment => ({
  reducedMotion: matches('(prefers-reduced-motion: reduce)'),
  finePointer: matches('(pointer: fine)'),
  wideViewport: matches('(min-width: 768px)'),
});
```

`PromptScene.tsx` renders `null` unless the eligibility helper returns true. When true, it uses `React.lazy(() => import('./PromptCanvas'))` inside `Suspense` so Three.js is not requested for fallbacks.

`PromptCanvas.tsx` renders a R3F `Canvas` with `aria-hidden`, one rounded-box/speech-bubble-inspired mesh, a small lightning-shaped line or plane, limited particles and blue/cyan/violet point lights. The pointer handler only updates mesh rotation; animation updates only `rotation` and `position`. The component stays decorative and must not contain product copy.

`HeroSection.astro` mounts `<PromptScene client:idle />` beside the static fallback, so the fallback remains available if client JavaScript or WebGL fails.

- [ ] **Step 4: Implement the GSAP lifecycle as a dynamic desktop-only import**

`ScrollNarrative.astro` gives its section `data-scroll-narrative` and each chapter `data-narrative-step`, then uses an inline module to call `import('../scripts/scrollNarrative')` only after `shouldUseScrollSequence` is true.

`scrollNarrative.ts` dynamically imports `gsap` and `gsap/ScrollTrigger`, registers `ScrollTrigger`, pins the narrative copy on desktop, animates only `opacity`, `transform` and `clip-path`, and returns a cleanup function that calls `context.revert()`. A `pagehide` listener invokes cleanup. Reduced motion and narrow viewports do not import GSAP.

- [ ] **Step 5: Re-run all frontend tests, type checks and production build**

Run: `npm test && npm run check && npm run build && npm run verify:build`

Expected: all tests pass, Astro has no type errors, and the static verifier exits 0.

- [ ] **Step 6: Commit the interaction layer**

```bash
git add site/src/components/PromptScene.tsx site/src/components/PromptCanvas.tsx site/src/components/HeroSection.astro site/src/components/ScrollNarrative.astro site/src/scripts/scrollNarrative.ts site/src/styles/global.css site/src/lib/experience.test.ts
git commit -m "feat: add immersive landing interactions"
```

### Task 5: Configure GitHub Pages and perform release verification

**Files:**
- Create: `.github/workflows/deploy-pages.yml`
- Modify: `README.md`

- [ ] **Step 1: Add the Pages deployment workflow**

```yaml
name: Deploy BoostPrompt site

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v6
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: site/package-lock.json
      - run: npm ci
        working-directory: site
      - run: npm run build
        working-directory: site
        env:
          GITHUB_ACTIONS: 'true'
      - uses: actions/upload-pages-artifact@v4
        with:
          path: site/dist
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Document local preview and expected Pages URL**

Add a “Landing page” subsection to `README.md` with exactly these commands and URL:

```bash
cd site
npm install
npm run dev
```

`https://airtonlira.github.io/boostprompt` is the expected URL while this repository remains owned by `AirtonLira`.

- [ ] **Step 3: Validate all deliverables from the worktree**

Run: `cd site && npm test && npm run check && GITHUB_ACTIONS=true npm run build && npm run verify:build && ! rg -n 'unsplash|picsum|placeholder|placehold|via\.placeholder|lorem\.space|dummyimage' src public dist`

Expected: all commands exit 0 and the final search has no matches.

- [ ] **Step 4: Commit deployment and documentation**

```bash
git add .github/workflows/deploy-pages.yml README.md
git commit -m "ci: deploy BoostPrompt landing to Pages"
```

## Final verification

- [ ] Run `uv run pytest` to confirm the Python project remains green.
- [ ] Run `cd site && npm test && npm run check && GITHUB_ACTIONS=true npm run build && npm run verify:build`.
- [ ] Run `git status --short` and inspect `git log --oneline main..HEAD` to report only landing-page commits.
