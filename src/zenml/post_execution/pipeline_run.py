#  Copyright (c) ZenML GmbH 2023. All Rights Reserved.
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
"""Implementation of the post-execution pipeline run class."""

from typing import List

from zenml.client import Client
from zenml.logger import get_logger
from zenml.models import PipelineRunResponseModel

logger = get_logger(__name__)


def get_run(name: str) -> "PipelineRunResponseModel":
    """Fetches the post-execution view of a run with the given name.

    Args:
        name: The name of the run to fetch.

    Returns:
        The post-execution view of the run with the given name.

    Raises:
        KeyError: If no run with the given name exists.
        RuntimeError: If multiple runs with the given name exist.
    """
    logger.warning(
        "`zenml.post_execution.get_run(<name>)` is deprecated and will be "
        "removed in a future release. Please use "
        "`zenml.client.Client().get_pipeline_run(<name>)` instead."
    )
    return Client().get_pipeline_run(name)


def get_unlisted_runs() -> List["PipelineRunResponseModel"]:
    """Fetches the post-execution views of the 50 most recent unlisted runs.

    Unlisted runs are runs that are not associated with any pipeline.

    Returns:
        A list of post-execution run views.
    """
    logger.warning(
        "`zenml.post_execution.get_unlisted_runs()` is deprecated and will be "
        "removed in a future release. Please use "
        "`zenml.client.Client().list_pipeline_runs(unlisted=True)` instead."
    )
    return Client().list_pipeline_runs(unlisted=True).items
