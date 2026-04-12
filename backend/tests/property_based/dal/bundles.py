"""Central bundle registry for DAL property-based tests.

This module provides a single source of truth for all bundles used across
the repository state machine rules. Using a central registry ensures:
- Explicit, IDE-navigable bundle references (Bundles.users vs Bundle("users"))
- Type safety and autocomplete support
- Easy refactoring (rename propagates everywhere)
- Clear dependency tracking (mixins import from here)

THREAD-SAFETY WARNING:
----------------------
These are shared Bundle instances. This state machine is NOT thread-safe and
should not be run in parallel processes or threads.

Why this matters:
- Hypothesis's default test runner is single-threaded, so this is safe for normal usage
- Multiple test processes (e.g., pytest -n 4) would share these Bundle instances
- This would cause cross-contamination between parallel test runs

Current status:
- ✅ Safe for current single-threaded usage
- ⚠️ Future limitation if parallel testing is needed

The current approach prioritizes clean syntax: @rule(target=Bundles.users)

For parallel testing in the future, alternative approaches would be needed.
"""

from hypothesis.stateful import Bundle


class Bundles:
    """Registry of all bundles for the DAL state machine.

    Each bundle represents a collection of entity IDs that can be used
    as inputs to rules that operate on those entities.

    Usage:
        @rule(target=Bundles.users)  # Adds result to users bundle
        @rule(user_id=Bundles.users)  # Draws from users bundle

    Thread-Safety:
        These are SHARED Bundle instances across all test runs.
        Not safe for parallel testing (pytest -n).
        See module docstring for details and alternatives.
    """

    users = Bundle("users")
    organizations = Bundle("organizations")
    projects = Bundle("projects")
    tickets = Bundle("tickets")
