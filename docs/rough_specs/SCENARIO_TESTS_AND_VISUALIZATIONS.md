# IMPLEMENTATION_SPECS.md
AI-Native Showcase – Implementation Guidelines for Coding Agents

## File 1 – Scenario Tests + Visual Evidence + Simple POC Viewer

### Goal
Create a repeatable, systematic way to write high-level acceptance/scenario tests with Playwright that automatically produce:
- Sequenced screenshots
- Short animated GIFs (actions-only, fast playback, 5-8 seconds)
- A simple web-based Evidence Viewer (POC) that displays, filters, searches, and reviews all visuals.

This becomes the core "first-class evidence" system for the AI-native codebase.

### Folder Structure to Create
tests/
e2e/
scenarios/              # all scenario tests go here
create-project-flow.spec.ts
update-epic-flow.spec.ts
...
fixtures/
helpers/
evidence/
screenshots/              # auto-generated PNGs (01-, 02-, etc.)
gifs/                     # auto-generated short GIFs
traces/                   # Playwright trace.zip files
gallery/                  # static HTML + JS for the POC viewer
tools/
generate-evidence.ts      # post-test script
text### Step-by-Step Implementation Instructions

1. Playwright Config (tests/e2e/playwright.config.ts)
   ```ts
   use: {
     screenshot: { mode: 'only-on-failure', fullPage: true },
     video: 'retain-on-failure',
     trace: 'on-first-retry',
     viewport: { width: 1280, height: 720 }
   }

Scenario Test Template (use this exact pattern for every new test)TypeScriptimport { test, expect } from '@playwright/test';
import fs from 'fs';

test('SCENARIO: Create Project Full Flow', async ({ page }) => {
  const correlationId = `test-create-project-${Date.now()}`;
  await page.addInitScript((id) => { (window as any).__CORRELATION_ID = id; }, correlationId);

  await page.goto('/projects');
  await page.screenshot({ path: 'evidence/screenshots/01-projects-list.png' });

  await page.getByRole('button', { name: 'New Project' }).click();
  await page.screenshot({ path: 'evidence/screenshots/02-new-project-modal.png' });

  await page.fill('[data-testid="project-name"]', 'AI-Native Demo');
  await page.click('text=Create');

  await expect(page.getByText('Project created')).toBeVisible();
  await page.screenshot({ path: 'evidence/screenshots/03-project-created.png' });

  fs.writeFileSync('evidence/metadata/create-project.json', JSON.stringify({
    name: 'Create Project Full Flow',
    correlationId,
    steps: 3,
    timestamp: new Date().toISOString()
  }));
});
Evidence Generation Script (tools/generate-evidence.ts)
Run after every test suite with: npm run evidence:generate
Converts videos → short GIFs using ffmpeg
Generates evidence/gallery/index.html

Simple POC Evidence Viewer (evidence/gallery/index.html + viewer.js)
Single static HTML file (no heavy framework needed for POC)
Left sidebar: Feature filter, Status chips (New/Changed/Passed), Search box
Main grid: Cards with GIF thumbnails (auto-play on hover)
Click any card → modal showing large GIF player + filmstrip of screenshots + metadata + "View Trace" + "Jump to Test Code"


Acceptance Criteria for File 1

Every scenario test automatically produces screenshots + GIF
One command (npm run evidence:generate) creates/updates the full gallery
Viewer works at http://localhost:3000/evidence (or as static HTML)
New/changed evidence is clearly highlighted