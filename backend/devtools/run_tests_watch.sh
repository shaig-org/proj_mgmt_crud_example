#!/usr/bin/env zsh
set -x

# --nobeep - by default, pytest-watch beeps whenever a test fails.
#   This is nice if you save files manually or only occasionaly, but if you're
#   saving on every keystrokes, then tests fail constantly whenever you're writing
#   code, and this becomes extremely annoying instead of beeing useful...
# -rP - display extra information on all non-passing tests. See:
#   https://docs.pytest.org/en/6.2.x/reference.html#command-line-flags
# pytest-watch - re-run tests on file changes
#   Needed pip installation of pytest-watch
# testmon - only run tests that can be impacted by the code that was changed.
#   (so you typically only run a small portion of the tests).
#   This works to some extent, but it's not perfect, so you sometimes want to omit it.
#   Needed pip installation of pytest-testmon
# rm .testmondata - when we start watching, we delete the testmon cache,
#   meaning we'll run all the tests once. We want this because it means that to clear
#   the cache, all we need to do is stop the tests and re-run them, and this is more
#   common than the need to avoid running all the tests when restarting the watch.
# rm .testmondata
# poetry run pytest-watch --nobeep -- --testmon -rP

rm -f .testmondata* || true
uv run pytest-watch --ext py,html --nobeep -- --testmon -rP
