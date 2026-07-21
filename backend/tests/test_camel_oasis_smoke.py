"""
camel-oasis smoke test — required by the Graphiti/FalkorDB migration's
dependency decision: installing graphiti-core[falkordb] pulls neo4j up to
6.2.0, which conflicts with camel-oasis==0.2.5's pinned neo4j==5.23.0
(see the override comment next to graphiti-core in pyproject.toml).

This exercises the actual oasis/camel code path used by
scripts/run_parallel_simulation.py (agent graph generation, environment
creation, one simulation round) with the LLM call itself mocked out, so a
change to the neo4j version showing up as an ImportError/AttributeError
deep inside oasis's own modules would fail here — not just a bare
`import oasis`.

Run from backend/ directory:
    pytest tests/test_camel_oasis_smoke.py -v
"""

import csv
import os
import tempfile
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def twitter_profile_csv():
    tmpdir = tempfile.mkdtemp(prefix="camel_oasis_smoke_")
    csv_path = os.path.join(tmpdir, "twitter_profiles.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_char", "username", "description"])
        writer.writerow([
            "A friendly test persona.",
            "smoke_test_user",
            "A single agent used only for the camel-oasis smoke test.",
        ])
    yield tmpdir, csv_path


@pytest.mark.asyncio
async def test_single_agent_single_round_no_import_or_attribute_errors(twitter_profile_csv):
    """1 agent, 1 round, LLM call mocked — verifies neo4j 6.2.0 doesn't break
    the oasis/camel code paths this project's simulation engine depends on."""
    import oasis
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    from oasis import ActionType, LLMAction, generate_twitter_agent_graph
    from oasis.social_agent.agent import SocialAgent

    tmpdir, csv_path = twitter_profile_csv

    # A real (but fake-keyed) camel model object — construction alone makes
    # no network call, and astep() below is mocked so none happens later either.
    os.environ.setdefault("OPENAI_API_KEY", "sk-smoketest-fake-key")
    model = ModelFactory.create(model_platform=ModelPlatformType.OPENAI, model_type="gpt-4o-mini")

    agent_graph = await generate_twitter_agent_graph(
        profile_path=csv_path,
        model=model,
        available_actions=[ActionType.CREATE_POST, ActionType.DO_NOTHING],
    )
    assert len(list(agent_graph.get_agents())) == 1

    class _FakeLLMResponse:
        info = {"tool_calls": []}

    original_astep = SocialAgent.astep
    SocialAgent.astep = AsyncMock(return_value=_FakeLLMResponse())
    try:
        db_path = os.path.join(tmpdir, "twitter_simulation.db")
        env = oasis.make(
            agent_graph=agent_graph,
            platform=oasis.DefaultPlatformType.TWITTER,
            database_path=db_path,
            semaphore=2,
        )
        await env.reset()

        actions = {agent: LLMAction() for _, agent in agent_graph.get_agents()}
        await env.step(actions)

        await env.close()
        assert os.path.exists(db_path)
    finally:
        SocialAgent.astep = original_astep
