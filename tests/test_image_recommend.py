"""Image recommendations stay anchored to the post — logo-only options are dropped."""

from __future__ import annotations

import json

import pytest

from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.image.recommend import _is_logo_only, recommend_images
from marketing_engine.sdk.client import FakeLLMClient, RunResult


def test_is_logo_only():
    assert _is_logo_only("Existing brand mark / wordmark over generous whitespace")
    assert _is_logo_only("The company logo, centered, monochrome lockup")
    # A real scene that merely mentions a logo watermark is NOT logo-only.
    assert not _is_logo_only("A photo of a family at a table; small logo watermark in corner")
    assert not _is_logo_only("Minimalist line diagram of a coin-stack flowing into a vault")


class _LogoHeavyFake(FakeLLMClient):
    """Returns one logo-only option plus two real scene options."""

    async def run(self, prompt, options):
        if "image SOURCE per option" in prompt:
            return RunResult(text=json.dumps({
                "core_idea": "x",
                "recommendation": "depict the idea",
                "options": [
                    {"kind": "library", "direction": "Existing brand mark / wordmark lockup", "rationale": "brand"},
                    {"kind": "generated", "direction": "Line diagram of the mechanic in the post", "rationale": "shows it"},
                    {"kind": "real_photo", "direction": "Photo of metal granules in a vault", "rationale": "tangible"},
                ],
            }), model="fake")
        return await super().run(prompt, options)


@pytest.mark.asyncio
async def test_recommend_drops_logo_only_option(settings):
    eng = MarketingEngine(settings, llm=_LogoHeavyFake())
    rec = await recommend_images(eng, "acme-co", "acme", post_text="A post about the mechanic.")
    dirs = [o.direction for o in rec.options]
    assert not any("wordmark" in d.lower() for d in dirs)  # logo-only dropped
    assert len(rec.options) == 2 and all(o.direction for o in rec.options)
