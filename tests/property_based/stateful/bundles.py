"""Central registry of all Hypothesis bundles for the system API state machine.

This module provides a single source of truth for all bundles used across
the state machine rules. Using a central registry ensures:
- Explicit, IDE-navigable bundle references (Bundles.users vs Bundle("users"))
- Type safety and autocomplete support
- Easy refactoring (rename propagates everywhere)
- Clear dependency tracking (mixins import from here)
"""

from hypothesis.stateful import Bundle


class Bundles:
    """Registry of all bundles for the system API state machine.

    Each bundle represents a collection of entity IDs that can be used
    as inputs to rules that operate on those entities.
    """

    users = Bundle("users")
    organizations = Bundle("organizations")
    projects = Bundle("projects")
    tickets = Bundle("tickets")
