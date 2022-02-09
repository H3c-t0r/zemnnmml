#  Copyright (c) ZenML GmbH 2022. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.

import logging


import pytest
from pydantic.main import BaseModel


from zenml.enums import MetadataContextTypes, StackComponentType
from zenml.orchestrators.context_utils import (
    add_pydantic_object_as_metadata_context,
)
from zenml.repository import Repository
from zenml.steps import step


from tfx.proto.orchestration.pipeline_pb2 import ContextSpec


def test_pipeline_storing_stack_in_the_metadata_store(
    clean_repo, one_step_pipeline
):
    """Tests that returning an object of a type that wasn't specified (either
    directly or as part of the `Output` tuple annotation) raises an error."""

    @step
    def some_step_1() -> int:
        return 3

    pipeline_ = one_step_pipeline(some_step_1())
    pipeline_.run()

    repo = Repository()

    stack = repo.get_stack(repo.active_stack_name)
    metadata_store = stack.metadata_store
    stack_contexts = metadata_store.store.get_contexts_by_type(
        MetadataContextTypes.STACK.value
    )

    assert len(stack_contexts) == 1

    assert stack_contexts[0].custom_properties[
        StackComponentType.ORCHESTRATOR.value
    ].string_value == stack.orchestrator.json(sort_keys=True)
    assert stack_contexts[0].custom_properties[
        StackComponentType.ARTIFACT_STORE.value
    ].string_value == stack.artifact_store.json(sort_keys=True)
    assert stack_contexts[0].custom_properties[
        StackComponentType.METADATA_STORE.value
    ].string_value == stack.metadata_store.json(sort_keys=True)


def test_pydantic_object_to_metadata_context():
    class Unjsonable:
        def __init__(self):
            self.value = "value"

    class StringAttributes(BaseModel):
        b: str
        a: str

    class MixedAttributes(BaseModel):
        class Config:
            arbitrary_types_allowed = True

        s: str
        f: float
        i: int
        b: bool
        l: list
        u: Unjsonable

    # straight-forward fully serializable object
    ctx1 = ContextSpec()
    obj1 = StringAttributes(b="bob", a="alice")
    add_pydantic_object_as_metadata_context(obj1, ctx1)
    assert ctx1.type.name == "stringattributes"
    assert ctx1.name.field_value.string_value == str(
        hash('{"a": "alice", "b": "bob"}')
    )

    # object with serialization difficulties
    ctx2 = ContextSpec()
    obj2 = MixedAttributes(
        s="steve", f=3.14, i=42, b=True, l=[1, 2], u=Unjsonable()
    )
    add_pydantic_object_as_metadata_context(obj2, ctx2)
    assert ctx2.type.name == "mixedattributes"
    assert ctx2.name.field_value.string_value.startswith("MixedAttributes")
    assert "s" in ctx2.properties.keys()
    assert ctx2.properties.get("b").field_value.int_value == 1
    assert ctx2.properties.get("l").field_value.string_value == "[1, 2]"
    assert "u" not in ctx2.properties.keys()
