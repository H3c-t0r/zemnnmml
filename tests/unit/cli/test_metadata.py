#  Copyright (c) ZenML GmbH 2020. All Rights Reserved.
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

import os

import pytest
from click.testing import CliRunner

from zenml.cli.metadata_store import (
    describe_metadata_store,
    list_metadata_stores,
    register_metadata_store,
)
from zenml.metadata_stores import SQLiteMetadataStore

NOT_LOGGING_LEVELS = ["abc", "my_cat_is_called_aria", "pipeline123"]
NOT_METADATA_STORES = ["abc", "my_other_cat_is_called_blupus", "pipeline456"]


@pytest.mark.xfail()
def test_metadata_register_actually_registers_new_metadata_store(
    tmp_path,
) -> None:
    """Test that the metadata register command actually registers a metadata store"""
    # TODO [ENG-337]: implement this test
    runner = CliRunner()
    test_metadata_dir = os.path.join(tmp_path, "metadata.db")

    result = runner.invoke(
        register_metadata_store,
        ["test_store", SQLiteMetadataStore(uri=test_metadata_dir)],
    )
    assert result.exit_code == 0


def test_metadata_list_lists_default_local_metadata_store() -> None:
    """Test that the metadata list command lists the default local metadata store"""
    # TODO [ENG-338]: add a fixture that spins up a test env each time
    runner = CliRunner()
    result = runner.invoke(list_metadata_stores)
    assert result.exit_code == 0
    assert "local_metadata_store" in result.output


def test_metadata_describe_contains_local_metadata_store() -> None:
    """Test that the metadata describe command contains the default local metadata store"""
    # TODO [ENG-339]: add a fixture that spins up a test env each time
    runner = CliRunner()
    result = runner.invoke(describe_metadata_store)
    assert result.exit_code == 0
    assert "local_metadata_store" in result.output


@pytest.mark.parametrize("not_a_metadata_store", NOT_METADATA_STORES)
def test_metadata_describe_fails_for_bad_input(
    not_a_metadata_store: str,
) -> None:
    """Test that the metadata describe command fails when passing in bad parameters"""
    # TODO [ENG-340]: add a fixture that spins up a test env each time
    runner = CliRunner()
    result = runner.invoke(describe_metadata_store, [not_a_metadata_store])
    assert result.exit_code == 1
