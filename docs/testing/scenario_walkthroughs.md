# Scenario Tests & Walkthroughs

Scenario tests are high-level, behavior-coverage E2E tests that double as **visual walkthroughs** of major user-visible flows. Every run produces auto-numbered screenshots, a metadata JSON, a video, and a Playwright trace. A local generator turns those artifacts into per-step flipbook GIFs, slowed motion GIFs, and a static **Dev Dashboard** for browsing.

This page is the canonical guide for both authoring scenarios and viewing the dashboard.

---

## What and why

- **What they are**: Playwright tests written with the `scenarioTest` fixture and bracketed by `step('label', async () => { ... })`. Each `step` produces a numbered screenshot of the resulting DOM state. Title plus steps form a guided tour of a feature.
- **Why they exist**: to give humans (PMs, reviewers, future engineers) a fast visual answer to "what does this feature actually look like end-to-end?" without spinning up the app — and to give us a thin, durable behavior smoke for the primary happy path.
- **What they are NOT**:
  - Not a replacement for unit, repository, domain, PBT, or API tests. Those still own business-logic correctness.
  - Not for exhaustive edge-case coverage — too slow, too heavy, screenshots become noise.
  - Not for negative paths or permission matrices — keep those at the API/E2E layer.

Rule of thumb: **if a PM would demo it, it deserves a scenario.**

---

## When to write one

- Every major user-facing feature must ship with **at least one scenario** covering its primary happy path.
- Aim for **5–8 steps**. Fewer than 4 is usually not a "flow"; more than 8 is usually two scenarios.
- One scenario per flow. Variants (different roles, different inputs) belong in regular E2E specs, not in additional scenarios.
- Backend-only features and pure refactors do NOT need a scenario. If a backend change alters an API consumed by an existing scenario, re-run scenarios as part of validation.

Edge cases, validation errors, permission boundaries, and business invariants stay in unit + PBT + API + regular E2E tests.

### Scope of the scenario-coverage rule

The "every major user-facing feature requires at least one scenario" rule applies to **new** user-facing features introduced from this PR onward. Existing features without a scenario may be backfilled opportunistically over time — a missing scenario on a pre-existing feature is not a blocker for unrelated work. If a change materially alters a flow that already has a scenario, update that scenario in the same PR.

---

## How to author a scenario

### File layout

- Location: `frontend/e2e/scenarios/<kebab-name>.scenario.spec.ts`
- Naming: `<feature-or-flow>.scenario.spec.ts` — e.g. `create-project.scenario.spec.ts`.
- Do NOT put regular specs under `e2e/scenarios/`. That directory is exclusive to the `scenarios` Playwright project.

### Minimal example

```ts
import { scenarioTest, step } from '../helpers/scenario';
import { generateTestProjectName } from '../helpers/test-data';

scenarioTest('Create project full flow', async ({ page }) => {
  const projectName = generateTestProjectName();

  await step('Open the projects page', async () => {
    await page.goto('/projects');
    await page.getByRole('heading', { name: 'Projects' }).waitFor();
  });

  await step('Open the create-project dialog', async () => {
    await page.getByRole('button', { name: 'New project' }).click();
    await page.getByRole('dialog').waitFor();
  });

  await step('Fill in the project name', async () => {
    await page.getByLabel('Name').fill(projectName);
  });

  await step('Submit and land on the new project', async () => {
    await page.getByRole('button', { name: 'Create' }).click();
    await page.getByRole('heading', { name: projectName }).waitFor();
  });
});
```

### Authoring rules

- **Title is human-readable.** It is shown verbatim in the Dev Dashboard. Use sentence case, e.g. `'Create project full flow'`, not `'createProject_happy'`.
- **Always wrap visible actions in `step('Short imperative label', ...)`.** The label is the caption for the screenshot/frame in the flipbook. Use imperative voice ("Open the dialog", "Submit the form") — short enough to fit in a card caption.
- **One visibly distinct DOM state per step.** If two adjacent steps land on identical-looking screens, the flipbook frame is wasted. Restructure: merge them, or insert a step that produces a real visual change (open menu, scroll into view, focus field).
- **UI-only inside the test body.** API setup belongs in `beforeAll`/`beforeEach`. No `page.request.post('/api/...')` between steps.
- **Parallel-safe data.** Use `generateTestProjectName()` and similar helpers; never reuse fixed strings across runs.
- **No `waitForTimeout`.** Wait on concrete conditions (`toBeVisible`, `toHaveValue`, `not.toBeDisabled`).
- **Never call `page.screenshot()` directly inside a scenario.** It bypasses the auto-numbering and will not appear in the flipbook in order. Use `step()` for everything that should be captured.

### What the fixture does for you

- Auto-numbers and saves a screenshot after each `step()`.
- Generates a correlation ID and emits a per-run metadata JSON (title, steps, timings, video path, trace path).
- Manually starts/stops a Playwright trace.
- Runs with `video: 'on'` at viewport 1600×900.
- Writes everything under `frontend/walkthroughs/` (gitignored).

---

## How to run

- `npm run e2e:scenarios` — runs the `scenarios` Playwright project only (fast feedback while authoring).
- `npm run e2e` — full E2E suite, includes the `scenarios` project. **Scenarios are part of the standard validation gate.**

Both must be zero-warning, zero-failure.

---

## Dev Dashboard (local visualization)

The Dev Dashboard is a static site that browses the latest scenario walkthroughs. **Dev-only — not part of CI.**

### Generate and serve

```sh
npm run walkthroughs:generate   # requires ffmpeg on PATH
npm run walkthroughs:serve      # http://localhost:4173
```

Typical loop: `npm run e2e:scenarios && npm run walkthroughs:generate && npm run walkthroughs:serve`.

> If you're updating from before the `evidence`→`walkthroughs` rename, wipe `frontend/walkthroughs/` once to remove stale entries.

### What the generator does

- Reads metadata JSONs and per-step screenshots from the latest run of each scenario (stale runs pruned, latest per scenario kept).
- Pads frames to a shared canvas so different resolutions don't break the flipbook.
- Produces:
  - **Flipbook GIF** — one frame per step, 1.5 s/frame, captions taken from `step()` labels.
  - **Motion GIF** — the source video at 2× slowed playback.
  - **Original `.webm`** — copied as-is.
- Writes `manifest.json` and copies static viewer assets from `frontend/src-walkthroughs-dashboard/` (committed) into `frontend/walkthroughs/gallery/` (generated, gitignored).

### Dashboard features

- Toggle between **GIF cards** (one card per scenario, flipbook auto-plays on hover) and **Screenshot strips** (S/M sized strip-rows per scenario).
- **Size slider** (160–1200 px) controls card/strip width.
- **Sticky/collapsible sidebar** with search and filters.
- **Detail page** per scenario — flipbook + motion GIFs + original video (with a 0.1×–2× speed selector) + a screenshots page and a flow page.
- **Lightbox** with keyboard nav (← → Esc) for screenshots.

---

## Conventions and pitfalls

- Walkthrough output (`frontend/walkthroughs/`) is gitignored. **Never commit generated artifacts.** The viewer SOURCE in `frontend/src-walkthroughs-dashboard/` IS committed.
- `ffmpeg` must be on PATH for the generator. The generator is **not** wired into CI.
- If two adjacent steps look identical in the flipbook, that's almost always a sign one step is redundant or a step is missing a visible action. Restructure the scenario rather than padding it.
- Don't depend on `fullPage` screenshot quirks; the generator normalizes resolutions across frames.
- Scenario titles and step labels show up verbatim in the dashboard — write them as if a stranger will read them, because they will.

---

## Validation gate

- Scenarios run as part of `npm run e2e`. They must pass with zero warnings.
- The walkthrough generator (`walkthroughs:generate`) and dashboard server (`walkthroughs:serve`) are **optional dev tooling** — not part of the validation contract.
