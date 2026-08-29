"""What can go wrong resolving a provider, as types rather than as messages.

Separate classes because the callers need different answers. A configuration
that cannot be read is an operator's problem and is the same for every request;
a model outside a provider's catalogue is this request's problem and the next
request may well succeed. Collapsing them into one exception makes the API layer
guess which HTTP status to answer with, and guessing there is how a
configuration fault ends up reported as a transient one.

**Nothing in this module may carry a credential.** Every message names the
provider, the endpoint, the file, or the field — never the value of a secret.
That is the same rule `db_safety.py` follows for URLs, for the same reason: a
diagnostic is the carrier that leaves the machine.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base for everything this package raises."""


class ConfigError(ProviderError):
    """The provider configuration cannot be used as it stands.

    Absent, unparseable, too permissive on disk, or declaring a provider without
    a field the framework needs. An operator has to fix a file.
    """


class UnknownProvider(ProviderError):
    """A provider was requested that the configuration does not declare."""


class UnknownModel(ProviderError):
    """A model was requested that the resolved provider's catalogue does not list.

    Distinct from `UnknownProvider` because the remedy differs: this one is
    usually a name meant for a different provider, and the message says which
    catalogue was searched.
    """


class MissingCredential(ProviderError):
    """The resolved provider needs a credential and none is configured.

    Raised rather than resolved-around. There is deliberately no fallback: a
    launch that quietly continued on another provider would run the work in a
    different frame, on a different bill, with nothing on the screen saying so.
    """


class IncompleteCredential(ProviderError):
    """A precedence level supplied half of the credential/endpoint pair.

    The two are one unit — a key authenticates against the endpoint it was issued
    for — so half of it from one level and half from another is a combination
    nobody wrote down. It yields a 401 at best and the wrong account at worst.
    """
