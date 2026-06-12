from __future__ import annotations

import pytest

from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.harness.validate import validate_post
from marketing_engine.sdk.client import FakeLLMClient


@pytest.mark.asyncio
async def test_validate_passes_with_fake(settings):
    engine = MarketingEngine(settings, llm=FakeLLMClient())
    brand = engine.registry.get_brand("acme-co", "acme")
    ok, reason = await validate_post(engine, brand, "A finished short post.")
    assert ok is True
    assert reason == ""


@pytest.mark.asyncio
async def test_validate_empty_post_passes(settings):
    engine = MarketingEngine(settings, llm=FakeLLMClient())
    brand = engine.registry.get_brand("acme-co", "acme")
    ok, _ = await validate_post(engine, brand, "   ")
    assert ok is True
