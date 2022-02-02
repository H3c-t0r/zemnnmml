#  Copyright (c) ZenML GmbH 2021. All Rights Reserved.
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

import platform

from zenml.constants import VALID_OPERATING_SYSTEMS
from zenml.environment import Environment


def test_environment_platform_info_correctness():
    """Checks that `Environment.get_system_info()` returns the correct
    platform"""
    system_id = platform.system()

    if system_id == "Darwin":
        system_id = "mac"
    elif system_id not in VALID_OPERATING_SYSTEMS:
        system_id = "unknown"

    assert system_id.lower() == Environment.get_system_info()["os"]


def test_environment_is_singleton():
    """Tests that environment is a singleton."""
    assert Environment() is Environment()


def test_environment_contextmanager_to_set_attributes():
    """Tests that the `_layer` context manager can be used to
    temporarily set attributes on the environment singleton."""
    env = Environment()

    assert env.step_is_running is False

    with Environment._layer(step_is_running=True):
        assert env.step_is_running is True

    assert env.step_is_running is False


def test_environment_nested_contextmanager():
    """Tests that the `_layer` context manager can be nested and used
    to overwrite existing attributes from outer context managers."""
    env = Environment()

    assert env.step_is_running is False
    with Environment._layer(step_is_running=True):
        assert env.step_is_running is True

        with Environment._layer(step_is_running=False):
            assert env.step_is_running is False

        assert env.step_is_running is True

    assert env.step_is_running is False
