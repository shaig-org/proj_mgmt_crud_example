# E2E flake follow-ups (deferred from the speed-up branch)

> Context: this branch landed E2E speedups (auth seeding, fast hasher, WAL,
> Date.now()-collision fix, dedicated-epic flake fixes). Three follow-up
> items were deferred to keep the merge tight. Pick them up next.

## Deferred items

### 1. Backend cross-session visibility race (the "Organization not found" bug)

**Symptom:** under E2E parallelism (≥6 Playwright workers), the user-create
endpoint occasionally returns
`400 - {"detail":"Organization not found"}` for an org that the same worker
just created via the org-create POST (which returned 200 with a valid id).

**What's been ruled out:**
- Not a `Date.now()` collision — fixed in this branch.
- Not the username 50-char limit — fixed in this branch.
- Pool-class is not the silver bullet:
  - **StaticPool** (current default for `is_testing=True`): seen in 2/5 runs at 6 workers.
  - **NullPool**: seen at similar rate at 6 workers.
- WAL mode + `busy_timeout=10000` are already enabled.

**Root-cause hypotheses to investigate:**
1. **Snapshot isolation across requests on the SAME connection (StaticPool):**
   Two FastAPI requests served on different threads share the single
   StaticPool connection; one thread's BEGIN/COMMIT can leave the connection
   in a state where the other thread's read transaction sees the pre-commit
   snapshot. SQLAlchemy `Session.close()` doesn't necessarily reset the
   underlying DBAPI transaction state when `check_same_thread=False`.
2. **WAL frame visibility on a fresh connection (NullPool):**
   New connection opens a read transaction at time T. If the org-create
   commit's WAL frame hasn't been flushed to the WAL-index by the time the
   user-create connection reads it, the org isn't visible. (Less likely
   than #1 but worth ruling out via `PRAGMA wal_autocheckpoint=1` or
   explicit checkpoint.)
3. **FastAPI dependency teardown ordering:**
   `get_session()` commits in its post-yield teardown. The HTTP response
   is sent BEFORE the teardown runs (verified by reading FastAPI source).
   This means the test gets 200 BEFORE the commit fires. The test's next
   request can race with the still-pending commit. Verifiable via a small
   pytest harness that fires concurrent POST org → POST user.

**Suggested fix path:**
Rewrite `get_session` to commit BEFORE yielding the response:

```python
@contextmanager
def get_session(self) -> Iterator[Session]:
    session = self.SessionLocal()
    try:
        yield session
        session.commit()  # already there; correct
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Actually this is fine — repository methods commit themselves (see
`OrganizationRepository.create` calling `self.session.commit()` directly).
So the commit IS done before the response returns. The race must be at the
SQLite/connection level.

Try in this order:
1. **`PRAGMA wal_autocheckpoint=1`** — force checkpoint after every commit.
   Cheaper than expected; verifies hypothesis #2.
2. **Explicit `engine.dispose()` between test runs** — rules out engine
   state leaking.
3. **Switch all sessions to a single per-request connection-scoped session**
   via `scoped_session(scopefunc=request_id)` — reduces thread contention.
4. **Replace SQLAlchemy with `aiosqlite` + raw queries** for E2E mode —
   nuclear option.

**Category-level test that should be added (per memory rule):**
A pytest test that fires N concurrent
`POST /api/organizations` followed by `GET /api/organizations/{id}` from
N threads, asserts every created org is immediately visible to its own
follow-up read AND to the other threads' reads. Belongs in
`backend/tests/api/test_concurrent_visibility.py`. Should reproduce the
race deterministically with `pytest-xdist -n auto`.

### 2. Add the category-level tests for the bugs already fixed in this branch

Per the project rule "every fix ships with a category-level test"
(`~/.claude/projects/.../memory/preference_test_with_every_fix.md`), the
following tests should be added:

- **`backend/tests/api/test_concurrent_visibility.py`** — see above. Covers
  bug category #1.
- **`backend/tests/utils/test_test_data_naming.py`** — generator output
  must (a) fit every backend field's `max_length`, (b) be unique across
  many concurrent calls. Covers bug category #2 (`Date.now()` collisions
  + 50-char username overflow).
- **E2E meta-test or lint:** ensure no spec uses raw `Date.now()` for
  fixture names — must go through the worker-namespaced generators in
  `e2e/utils/test-config.ts`. ESLint custom rule or a pytest collection
  test that grep-scans the spec files. Covers re-introduction of #2.
- **E2E meta-test for shared-fixture data leaks:** any test that asserts
  "X is empty" must create its OWN X, not reuse a `beforeAll` X. Could be
  enforced by lint that flags `expect(...).toContainText('No \\w+ yet')`
  or `0 of 0` patterns combined with shared-fixture variables. Pragmatic
  for now: add a comment in `frontend/CLAUDE.md` and trust review.

### 3. Push beyond 4-6 workers

Current steady state is N workers (whichever this branch ends on). If the
backend race in #1 is fully fixed, retry 8 workers and measure. The
machine has 11 cores — there should be headroom. Beyond 8 workers, the
likely next bottleneck is browser-context startup (Playwright spawns one
per worker).

## What this branch already did

- Auth seeding via `loginViaApi` (per-worker token cache, no UI login)
- `TestPasswordHasher` wired in under `E2E_TESTING=true` (~300ms → ~0.001ms per password op)
- WAL journal mode + `busy_timeout=10000` for file-based SQLite
- `lifespan` wipes the E2E DB on startup so the bootstrap admin gets a fast hash
- `loginViaApi` lives in `frontend/e2e/utils/auth.ts`; documented in `frontend/CLAUDE.md`
- Replaced `Test Org ${Date.now()}` / `Test Project ${Date.now()}` /
  `pm${Date.now()}` with worker-namespaced generators across 9 spec files
- Shortened `generateTestUserName` to fit the backend's 50-char username cap
- Fixed three data-isolation flakes in `epic-details.spec.ts` by giving
  the affected tests their own dedicated epics
- Cross-stack `run-all-validations.sh` orchestrator added
