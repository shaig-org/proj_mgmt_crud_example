# Frontend Development Guidelines

This file provides guidance to Claude Code when working with the frontend code in this repository.

## Technology Stack

- **React 19** + **TypeScript** (strict mode)
- **Vite** - Fast build tool and dev server
- **Axios** - HTTP client for API calls
- **Playwright** - End-to-end testing
- **ESLint** - Code linting

## Zero Tolerance Policy

Before responding to the user, ALL of the following validations MUST pass with ZERO errors and ZERO warnings:

- ✅ `npm run lint` - ZERO errors, ZERO warnings
- ✅ `npm run typecheck` - ZERO TypeScript errors
- ✅ `npm run e2e` - 100% pass rate, ZERO skipped tests, ZERO failures

**🚨 CRITICAL: ALL TESTS MUST PASS 🚨**

- You MUST NEVER leave failing tests
- You MUST NEVER skip tests (except for known flaky infrastructure issues)
- If tests fail, you MUST fix them before completing your work
- If you cannot fix the tests, you MUST ask the user for help
- A feature is NOT complete until all tests pass

## Test-First Development

**🚨 ALWAYS WRITE TESTS FOR NEW CODE 🚨**

When implementing new features:

1. **Write E2E tests FIRST** - Before or immediately after writing the implementation
2. **Use Playwright MCP when available** - Prefer using the Playwright MCP server tools for test development when possible
3. **Comprehensive coverage** - Test all user flows, edge cases, and error conditions
4. **NO code without tests** - Every new feature MUST have corresponding E2E tests
5. **Run tests before committing** - Ensure all tests pass before marking work complete

**Test Coverage Requirements**:
- ✅ Happy path (feature works as expected)
- ✅ Edge cases (empty states, boundary conditions)
- ✅ Error handling (invalid inputs, permission errors)
- ✅ State persistence (data survives page reload)
- ✅ UI interactions (buttons, dropdowns, forms work correctly)

## Mandatory Validation Commands

Run these commands before every response to the user:

```bash
npm run lint
npm run typecheck
npm run e2e
```

If ANY of these fail, you MUST fix the issues before responding to the user.

## E2E Testing Rules

### 🚨 CRITICAL: ALWAYS RUN HEADLESS 🚨

**NEVER use `--headed` flag when running E2E tests automatically.**

- ✅ **CORRECT**: `npm run e2e` (headless with list reporter)
- ❌ **WRONG**: `npm run e2e:headed` (opens browser UI and blocks)
- ❌ **WRONG**: `playwright test --ui` (opens UI and blocks)

**Why?** Headed mode and UI mode serve an HTML report that blocks the terminal, preventing you from continuing work. This causes you to get stuck.

**For debugging only:** User can manually run `npm run e2e:headed` or `npm run e2e:ui` if they want to see the browser.

### E2E Testing Best Practices

1. **Always use list reporter**: Tests use `--reporter=list` to avoid HTML report blocking

2. **UI interactions only - NO direct API calls in tests**:
   - ❌ **WRONG**: `await page.request.post('/api/tickets', {...})` inside a test
   - ✅ **CORRECT**: Click buttons, fill forms, interact with UI elements
   - **Exception**: API calls are acceptable in `beforeAll`/`beforeEach` for test setup/fixtures (creating users, orgs, projects)
   - **Why**: E2E tests validate the entire user journey through the UI, not just the API

3. **NEVER use `waitForTimeout()` - wait for actual UI changes**:
   - ❌ **WRONG**: `await page.waitForTimeout(500)` - arbitrary wait
   - ✅ **CORRECT**: `await expect(element).toBeVisible()` - wait for specific state
   - ✅ **CORRECT**: `await expect(element).not.toBeDisabled()` - wait for interaction to complete
   - ✅ **CORRECT**: `await expect(element).toHaveValue('expected')` - wait for value change
   - **Why**: Playwright auto-waits and tests finish immediately when conditions are met, making tests faster and more reliable

4. **Parallel-safe tests**: Tests must work with 4 workers running in parallel

5. **Test isolation**: Each test should be independent and not rely on others

6. **Clean data**: Tests should create their own data and not depend on existing state

7. **Use `beforeAll` for shared fixtures**: When multiple tests can share the same setup (org/user/project), use `beforeAll` instead of `beforeEach` to reduce test time

### Running E2E Tests

```bash
# Standard headless run (use this for validation)
npm run e2e

# Debugging only (user can run manually)
npm run e2e:headed    # Opens browser
npm run e2e:ui        # Opens Playwright UI
npm run e2e:debug     # Opens debug mode
```

## API Integration

The frontend connects to the backend API:

- **Development**: `http://localhost:8000`
- **E2E Testing**: Backend starts automatically via Playwright webServer config

All API calls go through the centralized client in `src/services/api.ts`.

## Project Structure

```
frontend/
├── src/
│   ├── App.tsx              # Main application component
│   ├── main.tsx             # React entry point
│   ├── index.css            # Global styles
│   └── services/
│       └── api.ts           # API client service
├── e2e/                     # End-to-end tests (Playwright)
│   └── health-check.spec.ts # Health check tests
├── playwright.config.ts     # Playwright configuration
├── vite.config.ts           # Vite configuration
└── package.json             # Dependencies and scripts
```

## Development Workflow

1. **Make changes** to code
2. **Run linting**: `npm run lint`
3. **Run type checking**: `npm run typecheck`
4. **Run E2E tests**: `npm run e2e` (ALWAYS HEADLESS)
5. **Fix any failures** (zero tolerance)
6. **Show summary to user**
7. **Ask for commit approval**

## Common Issues

### Tests failing with "element not found"
- Use `await page.waitForSelector()` or `await expect().toBeVisible()`
- Check that the backend is returning correct data
- Verify API client is using correct endpoint format

### Port conflicts
- Frontend dev server uses port 3000 (or 3001 if 3000 is in use)
- Backend API uses port 8000
- Playwright manages servers automatically during tests

## Backend Integration

The backend must be running for the frontend to work:

```bash
# From project root
uv run uvicorn project_management_crud_example.app:app --reload --port 8000
```

During E2E tests, Playwright starts the backend automatically.
