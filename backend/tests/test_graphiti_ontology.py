"""
Tests for graphiti_ontology.convert_ontology() — converts the existing
(originally Zep-shaped) ontology dict into the entity_types / edge_types /
edge_type_map three-tuple that Graphiti's add_episode() expects.

Run from backend/ directory:
    pytest tests/test_graphiti_ontology.py -v
"""

from typing import Optional

import pytest
from pydantic import BaseModel

from app.services.graphiti_ontology import (
    DEFAULT_ENTITY_LABEL,
    convert_ontology,
)


@pytest.fixture
def sample_ontology():
    return {
        "entity_types": [
            {
                "name": "Person",
                "description": "A person entity.",
                "attributes": [
                    {"name": "age", "description": "The person's age."},
                    {"name": "occupation", "description": "The person's job."},
                ],
            },
            {
                "name": "Organization",
                "description": "An organization entity.",
                "attributes": [
                    {"name": "industry", "description": "The organization's industry."},
                ],
            },
        ],
        "edge_types": [
            {
                "name": "works_at",
                "description": "Person works at an organization.",
                "attributes": [
                    {"name": "role", "description": "The role held."},
                ],
                "source_targets": [
                    {"source": "Person", "target": "Organization"},
                ],
            },
            {
                "name": "knows",
                "description": "Person knows another person.",
                "attributes": [],
                "source_targets": [
                    {"source": "Person", "target": "Person"},
                ],
            },
        ],
    }


def test_entity_types_built_as_pydantic_models(sample_ontology):
    entity_types, _, _ = convert_ontology(sample_ontology)

    assert set(entity_types.keys()) == {"Person", "Organization"}
    assert issubclass(entity_types["Person"], BaseModel)
    assert entity_types["Person"].__doc__ == "A person entity."
    assert set(entity_types["Person"].model_fields.keys()) == {"age", "occupation"}
    assert entity_types["Person"].model_fields["age"].description == "The person's age."


def test_edge_types_built_as_pydantic_models(sample_ontology):
    _, edge_types, _ = convert_ontology(sample_ontology)

    assert set(edge_types.keys()) == {"works_at", "knows"}
    assert edge_types["works_at"].__doc__ == "Person works at an organization."
    assert set(edge_types["works_at"].model_fields.keys()) == {"role"}
    assert edge_types["knows"].model_fields == {}


def test_edge_type_map_inverts_source_targets_correctly(sample_ontology):
    _, _, edge_type_map = convert_ontology(sample_ontology)

    assert edge_type_map[("Person", "Organization")] == ["works_at"]
    assert edge_type_map[("Person", "Person")] == ["knows"]
    assert len(edge_type_map) == 2


def test_multiple_edge_types_can_share_same_source_target_pair():
    ontology = {
        "entity_types": [
            {"name": "Person", "description": "A person.", "attributes": []},
        ],
        "edge_types": [
            {
                "name": "likes",
                "description": "Person likes another person.",
                "attributes": [],
                "source_targets": [{"source": "Person", "target": "Person"}],
            },
            {
                "name": "distrusts",
                "description": "Person distrusts another person.",
                "attributes": [],
                "source_targets": [{"source": "Person", "target": "Person"}],
            },
        ],
    }

    _, _, edge_type_map = convert_ontology(ontology)

    assert set(edge_type_map[("Person", "Person")]) == {"likes", "distrusts"}


def test_edge_type_without_source_targets_is_not_added_to_map():
    ontology = {
        "entity_types": [],
        "edge_types": [
            {
                "name": "related_to",
                "description": "A generic relation with no direction constraint.",
                "attributes": [],
                "source_targets": [],
            },
        ],
    }

    _, edge_types, edge_type_map = convert_ontology(ontology)

    assert "related_to" in edge_types
    assert edge_type_map == {}


def test_missing_source_or_target_falls_back_to_default_entity_label():
    ontology = {
        "entity_types": [
            {"name": "Person", "description": "A person.", "attributes": []},
        ],
        "edge_types": [
            {
                "name": "mentions",
                "description": "Mentions something unspecified.",
                "attributes": [],
                "source_targets": [{"source": "Person", "target": ""}],
            },
        ],
    }

    _, _, edge_type_map = convert_ontology(ontology)

    assert edge_type_map[("Person", DEFAULT_ENTITY_LABEL)] == ["mentions"]


def test_reserved_attribute_names_are_renamed_for_entities():
    ontology = {
        "entity_types": [
            {
                "name": "Person",
                "description": "A person.",
                "attributes": [
                    {"name": "name", "description": "Collides with EntityNode.name."},
                    {"name": "summary", "description": "Collides with EntityNode.summary."},
                    {"name": "role", "description": "Does not collide."},
                ],
            },
        ],
        "edge_types": [],
    }

    entity_types, _, _ = convert_ontology(ontology)
    fields = entity_types["Person"].model_fields

    assert "name" not in fields
    assert "summary" not in fields
    assert "attr_name" in fields
    assert "attr_summary" in fields
    assert "role" in fields


def test_reserved_attribute_names_are_renamed_for_edges():
    ontology = {
        "entity_types": [],
        "edge_types": [
            {
                "name": "works_at",
                "description": "Works at.",
                "attributes": [
                    {"name": "fact", "description": "Collides with EntityEdge.fact."},
                    {"name": "role", "description": "Does not collide."},
                ],
                "source_targets": [],
            },
        ],
    }

    _, edge_types, _ = convert_ontology(ontology)
    fields = edge_types["works_at"].model_fields

    assert "fact" not in fields
    assert "attr_fact" in fields
    assert "role" in fields


def test_empty_ontology_returns_empty_structures():
    entity_types, edge_types, edge_type_map = convert_ontology({})

    assert entity_types == {}
    assert edge_types == {}
    assert edge_type_map == {}


def test_dynamic_models_pass_graphiti_validate_entity_types(sample_ontology):
    """Guards against re-introducing a reserved-name collision that Graphiti's
    own validate_entity_types() would reject at add_episode() time."""
    from graphiti_core.utils.ontology_utils.entity_types_utils import (
        validate_entity_types,
    )

    entity_types, _, _ = convert_ontology(sample_ontology)
    assert validate_entity_types(entity_types) is True
