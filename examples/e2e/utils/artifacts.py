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


from typing import Annotated
from uuid import UUID

from zenml.client import Client
from zenml.logger import get_logger

logger = get_logger(__name__)


def find_artifact_id(
    pipeline_name: str,
    artifact_name: str,
) -> Annotated[UUID, "artifact_id"]:
    """Find Artifact ID in Artifact Store.

    Args:
        pipeline_name: Name of a pipeline, which generated Artifact.
        pipeline_name: Name of an Artifact to search for.

    Raises:
        ValueError: If Artifact cannot be found.

    Returns:
        UUID: Found UUID in Artifact Store
    """
    pipeline = Client().get_pipeline(pipeline_name)
    latest_run = pipeline.runs[0]
    for artifact in latest_run.artifacts:
        if artifact.name == artifact_name:
            return artifact.id
    else:
        raise ValueError(
            f"`{artifact_name}` not found in last run of pipeline `{pipeline_name}`"
        )
