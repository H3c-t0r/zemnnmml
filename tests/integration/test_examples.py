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
import os
from collections import namedtuple
from distutils.dir_util import copy_tree
from pathlib import Path

import pytest

from zenml.cli import EXAMPLES_RUN_SCRIPT, SHELL_EXECUTABLE, LocalExample

from .example_validations import (
    caching_example_validation,
    drift_detection_example_validation,
    generate_basic_validation_function,
    mlflow_tracking_example_validation,
)


def example_runner(examples_dir):
    """Get the executable that runs examples.

    By default returns the path to an executable .sh file in the
    repository, but can also prefix that with the path to a shell
    / interpreter when the file is not executable on its own. The
    latter option is needed for windows compatibility.
    """
    return (
        [os.environ[SHELL_EXECUTABLE]] if SHELL_EXECUTABLE in os.environ else []
    ) + [str(examples_dir / EXAMPLES_RUN_SCRIPT)]


ExampleIntegrationTestConfiguration = namedtuple(
    "ExampleIntegrationTestConfiguration", ["name", "validation_function"]
)
examples = [
    ExampleIntegrationTestConfiguration(
        name="quickstart",
        validation_function=generate_basic_validation_function(
            pipeline_name="mnist_pipeline", step_count=3
        ),
    ),
    ExampleIntegrationTestConfiguration(
        name="not_so_quickstart",
        validation_function=generate_basic_validation_function(
            pipeline_name="mnist_pipeline", step_count=4, run_count=3
        ),
    ),
    ExampleIntegrationTestConfiguration(
        name="caching", validation_function=caching_example_validation
    ),
    ExampleIntegrationTestConfiguration(
        name="custom_materializer",
        validation_function=generate_basic_validation_function(
            pipeline_name="pipe", step_count=2
        ),
    ),
    ExampleIntegrationTestConfiguration(
        name="fetch_historical_runs",
        validation_function=generate_basic_validation_function(
            pipeline_name="mnist_pipeline", step_count=3
        ),
    ),
    # ExampleIntegrationTestConfiguration(
    #     name="kubeflow",
    #     validation_function=generate_basic_validation_function(
    #         pipeline_name="mnist_pipeline", step_count=4
    #     ),
    # ),
    ExampleIntegrationTestConfiguration(
        name="drift_detection",
        validation_function=drift_detection_example_validation,
    ),
    ExampleIntegrationTestConfiguration(
        name="mlflow_tracking",
        validation_function=mlflow_tracking_example_validation,
    ),
    # TODO [HIGH]: Enable running the whylogs example on kubeflow
    # ExampleIntegrationTestConfiguration(
    #     name="whylogs", validation_function=whylogs_example_validation
    # ),
]


@pytest.mark.parametrize(
    "example_configuration",
    [pytest.param(example, id=example.name) for example in examples],
)
@pytest.mark.parametrize(
    "repo_fixture_name", ["clean_repo"]  # , "clean_kubeflow_repo"]
)
def test_run_example(
    example_configuration: ExampleIntegrationTestConfiguration,
    repo_fixture_name,
    request,
):
    """Runs the given examples and validates they ran correctly."""
    # run the fixture given by repo_fixture_name
    repo = request.getfixturevalue(repo_fixture_name)

    # Root directory of all checked out examples
    examples_directory = Path(repo.original_cwd) / "examples"

    # Copy all example files into the repository directory
    # this uses a distutil method as shutil.copytree only has a dirs_exist_ok
    # parameter only since python 3.8
    copy_tree(
        str(examples_directory / example_configuration.name), str(repo.root)
    )

    # Run the example
    example = LocalExample(name=example_configuration.name, path=repo.root)
    example.run_example(
        example_runner(examples_directory),
        force=True,
        prevent_stack_setup=True,
    )

    # Validate the result
    example_configuration.validation_function(repo)
