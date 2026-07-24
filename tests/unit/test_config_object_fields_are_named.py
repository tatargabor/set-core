"""A caller who must guess a field name gets the empty shape, not an error.

Covers both config objects a caller reaches into by name: `StatusConfig` and `GateConfig`.

Raised by an integration peer who ran this layer against their own tree: they reached for
`getattr(cfg, "read_commands", ())` — a field that does not exist; the real name is
`commands` — got `()`, and was one step from reporting that set-core sees nothing from
their project, about a tree whose nine contract commands all answer in 2 seconds.

**The language supplies the proxy.** `getattr(o, name, default)` and `dict.get(key, default)`
do not fail on a wrong name; they return the default, which is the same value a genuinely
empty declaration produces. So a misread is indistinguishable from real absence, and it
fails in the reassuring direction — silence that reads as "nothing to show".

They caught it by a CONTRADICTION inside the same object (zero read commands while
`primary` named one), not by care, which is the honest reason this test exists rather than
a note asking people to be careful.

The cheap structural fix is that the docstring enumerates the fields, so nobody has to
guess. A docstring asks to be believed; this test refuses to let it drift.
"""

import dataclasses

from set_orch.project_status import StatusConfig


def test_status_config_docstring_names_every_field():
    doc = StatusConfig.__doc__ or ""
    missing = [f.name for f in dataclasses.fields(StatusConfig)
               if f"`{f.name}`" not in doc]

    assert missing == [], (
        f"fields absent from the docstring: {missing}. A caller who cannot read the name "
        f"off the documentation guesses it, and a wrong guess returns the empty shape "
        f"rather than an error — see this module's docstring.")


def test_the_docstring_names_no_field_that_does_not_exist():
    """The mirror: a documented-but-removed name is worse than an undocumented one.

    It is the shape a caller would confidently reach for, and it would resolve to the
    default — the same silent empty as the guess this file exists to prevent.
    """
    import re

    doc = StatusConfig.__doc__ or ""
    real = {f.name for f in dataclasses.fields(StatusConfig)}
    # Only the explicit enumeration paragraph, so ordinary prose in backticks is not
    # mistaken for a field name.
    para = doc.split("**Every field, by name")[1].split("A caller who")[0]
    named = set(re.findall(r"`([a-z_]+)`", para))

    assert named - real == set(), f"docstring names non-existent field(s): {named - real}"
    assert real - named == set(), f"enumeration is missing: {real - named}"


# ── the same class, third instance: GateConfig ────────────────────────────────────


def test_gate_config_docstring_names_every_attr():
    """`getattr(cfg, "gates", {})` returns an empty map; the real attribute is `_gates`.

    Third occurrence of this class reported in a single day by one integration peer
    (`j.bugs` under an envelope, `read_commands` for `commands`, `gates` for `_gates`), and
    the reason the fix is an enumeration held in a test rather than a note asking for care.

    `GateConfig` is a plain class, not a dataclass, so the field list comes from an
    instance's `vars()` — which is also exactly what a caller should inspect.
    """
    from set_orch.gate_profiles import GateConfig

    doc = GateConfig.__doc__ or ""
    attrs = sorted(vars(GateConfig()))
    missing = [a for a in attrs if f"`{a}`" not in doc]

    assert missing == [], (
        f"attributes absent from the docstring: {missing}. An empty gate map reads as "
        f"'nothing configured' rather than 'I spelled it wrong'.")


def test_the_gate_config_docstring_names_no_attr_that_does_not_exist():
    import re

    from set_orch.gate_profiles import GateConfig

    doc = GateConfig.__doc__ or ""
    real = set(vars(GateConfig()))
    para = doc.split("**Every attribute, by name.**")[1].split("The gate modes live")[0]
    named = set(re.findall(r"`([A-Za-z_]+)`", para))

    assert named == real, f"docstring/reality mismatch: {named ^ real}"
