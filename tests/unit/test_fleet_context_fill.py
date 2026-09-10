"""How full an agent's context is, and what is said when that cannot be known.

The half worth testing hardest is the unmeasured one. A window guessed for an
unfamiliar model produces a plausible wrong percentage that no reader can check,
and a zero fill emitted for an agent nobody measured reads as an agent holding
nothing — the opposite of the truth, and calm on screen either way.
"""

from __future__ import annotations

import pytest

from set_orch.fleet.context_fill import (
    CRITICAL_FRACTION,
    WARNING_FRACTION,
    band_for,
    context_payload,
    normalise_model,
    resolve_window,
)


class TestResolveWindow:
    """The window comes from the model name, and only from a name it knows."""

    @pytest.mark.parametrize("model,expected", [
        ("claude-opus-5", 200_000),
        ("claude-sonnet-4-6", 200_000),
        ("glm-5.3-flash", 900_000),
        ("gpt-6-astra", 272_000),
        ("gpt-5.6-luna", 272_000),
    ])
    def test_known_families_resolve(self, model, expected):
        assert resolve_window(model) == expected

    def test_million_variant_beats_the_family(self):
        """`claude-opus-5[1m]` also contains `claude-`; the marker must win.

        Checked as its own case because the family table would otherwise answer
        200 000 for a million-token session — a fifth of the real window, and
        wrong in the direction that cries wolf.
        """
        assert resolve_window("claude-opus-5[1m]") == 1_000_000
        assert resolve_window("claude-opus-5") == 200_000

    def test_gateway_prefix_is_stripped(self):
        """A gateway rewrites the id, and the prefix reaches this table.

        Measured against the local clodex endpoint, whose catalogue lists
        `anthropic-openai-oauth__gpt-6-astra`. Without stripping, an Astra agent
        resolves to nothing and shows as unmeasured forever.
        """
        assert resolve_window("anthropic-openai-oauth__gpt-6-astra") == 272_000

    @pytest.mark.parametrize("model", [None, "", "   ", "some-unknown-model-9"])
    def test_unknown_is_none_never_a_default(self, model):
        """An unknown name resolves to None, never to a default window.

        This is the whole safety property: a default would attach a plausible
        wrong denominator to exactly the model a reader cannot check, silently.
        """
        assert resolve_window(model) is None


class TestBands:
    def test_boundaries_are_inclusive_at_the_named_values(self):
        assert band_for(WARNING_FRACTION - 0.01) == "normal"
        assert band_for(WARNING_FRACTION) == "warning"
        assert band_for(CRITICAL_FRACTION - 0.01) == "warning"
        assert band_for(CRITICAL_FRACTION) == "critical"


class TestContextPayload:
    """The payload states figures, or states why it has none. Never a zero."""

    def test_measured_carries_window_and_fill(self):
        out = context_payload({"tokens": 212_000, "model": "gpt-6-astra"})["context"]
        assert out["state"] == "measured"
        assert out["window"] == 272_000
        assert out["tokens"] == 212_000
        assert out["fill"] == pytest.approx(212_000 / 272_000, abs=1e-4)
        assert out["band"] == "warning"

    def test_same_tokens_differ_by_window(self):
        """The reason this change exists: one count, two verdicts.

        212 000 tokens is most of an Astra window and a quarter of a GLM one.
        A shared denominator would report these as the same figure.
        """
        astra = context_payload({"tokens": 212_000, "model": "gpt-6-astra"})["context"]
        glm = context_payload({"tokens": 212_000, "model": "glm-5.3-flash"})["context"]
        assert astra["band"] == "warning"
        assert glm["band"] == "normal"
        assert astra["fill"] > glm["fill"]

    def test_no_cache_is_unmeasured_with_a_reason(self):
        out = context_payload(None)["context"]
        assert out["state"] == "unmeasured"
        assert out["reason"]
        assert "fill" not in out and "window" not in out

    def test_unknown_model_is_unmeasured_and_names_the_model(self):
        out = context_payload({"tokens": 5_000, "model": "mystery-1"})["context"]
        assert out["state"] == "unmeasured"
        assert "mystery-1" in out["reason"]
        # The token count is still reported: it was measured. Only the window
        # was not, and dropping the tokens too would discard a real figure.
        assert out["tokens"] == 5_000
        assert "fill" not in out

    def test_missing_tokens_is_unmeasured(self):
        out = context_payload({"model": "gpt-6-astra"})["context"]
        assert out["state"] == "unmeasured"
        assert "fill" not in out

    def test_never_emits_a_zero_window_or_zero_fill_when_unmeasured(self):
        """The property, across every unmeasured route — not one example.

        A zero window or a zero fill is a claim that the agent consumed nothing,
        which is the most confident and least true thing this record can say.
        """
        for cache in (None, {}, {"model": "gpt-6-astra"}, {"tokens": 1, "model": "mystery-1"},
                      {"tokens": "not-a-number", "model": "gpt-6-astra"},
                      {"tokens": -5, "model": "gpt-6-astra"}):
            out = context_payload(cache)["context"]
            if out["state"] == "unmeasured":
                assert out.get("window") != 0
                assert out.get("fill") != 0
                assert "window" not in out or out["window"] is None

    def test_the_key_is_always_present(self):
        """An unmeasured agent must be COUNTABLE on the header.

        `_cache_payload` omits itself when it has nothing; this deliberately
        does not. An absent key cannot be counted, and an uncounted agent is
        indistinguishable from an agent that does not exist.
        """
        assert "context" in context_payload(None)
        assert "context" in context_payload({"tokens": 1, "model": "gpt-6-astra"})

    def test_over_window_means_the_WINDOW_is_wrong_not_that_the_agent_is_full(self):
        """A context cannot exceed its own window, so a fill above 1 is evidence
        the window is wrong — never a 214 % agent.

        Measured 2026-09-08 on the live fleet: 3 of 7 agents came back above 1.0,
        every one a million-token session whose transcript records the model with
        the `[1m]` marker dropped. Reporting those as critical would put a red
        mark on nearly half the fleet for a limit none of them is near, and a
        mark that cries wolf on its first day is not read on its second.
        """
        out = context_payload({"tokens": 300_000, "model": "gpt-6-astra"})["context"]
        assert out["state"] == "unmeasured"
        assert "fill" not in out and "band" not in out
        assert "exceeds the window" in out["reason"]
        # The measured half is still reported; only the ratio is withheld.
        assert out["tokens"] == 300_000

    def test_exactly_at_the_window_is_still_measured(self):
        """The boundary belongs to the measurable side: a full context is a real
        state, and only a figure LARGER than the window is impossible."""
        out = context_payload({"tokens": 272_000, "model": "gpt-6-astra"})["context"]
        assert out["state"] == "measured"
        assert out["fill"] == 1.0
        assert out["band"] == "critical"


class TestNormalise:
    def test_blank_is_not_a_model_called_empty_string(self):
        assert normalise_model("   ") is None
        assert normalise_model(None) is None
