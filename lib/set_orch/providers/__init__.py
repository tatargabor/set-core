"""Provider and model selection for agents the framework starts.

Two exits, named separately on purpose:

- `resolve()` returns a `LaunchPlan` — the environment (credential included),
  the argv extras and the provenance. It never leaves the process.
- `catalogue()` returns provider and model NAMES and a usable flag. It is what a
  surface may be shown, and its return value has no field a credential could
  occupy.

They are two functions rather than one with a `redact=` flag because a flag has a
default, and a default that flips the wrong way publishes a token.
"""

from .config import (
    CONFIG_NAME, LEGACY_NAME, Credential, ProjectOverride, Provider,
    ProvidersConfig, config_dir, config_path, legacy_path, load,
)
from .errors import (
    ConfigError, IncompleteCredential, MissingCredential, ProviderError,
    UnknownModel, UnknownProvider,
)
from .resolver import (
    FOREIGN_KEYS, LEVEL_DEFAULT, LEVEL_PROJECT, LEVEL_REQUEST, LaunchPlan,
    catalogue, resolve,
)

__all__ = [
    "CONFIG_NAME", "LEGACY_NAME", "Credential", "ProjectOverride", "Provider",
    "ProvidersConfig", "config_dir", "config_path", "legacy_path", "load",
    "ConfigError", "IncompleteCredential", "MissingCredential", "ProviderError",
    "UnknownModel", "UnknownProvider",
    "FOREIGN_KEYS", "LEVEL_DEFAULT", "LEVEL_PROJECT", "LEVEL_REQUEST",
    "LaunchPlan", "catalogue", "resolve",
]
