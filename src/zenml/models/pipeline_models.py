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
"""Model definitions for pipelines, runs, steps, and artifacts."""

from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, cast
from uuid import UUID

from pydantic import BaseModel, Field

from zenml import __version__ as current_zenml_version
from zenml.config.global_config import GlobalConfiguration
from zenml.enums import ArtifactType
from zenml.models.project_models import ProjectModel
from zenml.models.user_management_models import UserModel
from zenml.utils.analytics_utils import AnalyticsTrackedModelMixin


def get_git_sha(clean: bool = True) -> Optional[str]:
    """Returns the current git HEAD SHA.

    If the current working directory is not inside a git repo, this will return
    `None`.

    Args:
        clean: If `True` and there any untracked files or files in the index or
            working tree, this function will return `None`.

    Returns:
        The current git HEAD SHA or `None` if the current working directory is
        not inside a git repo.
    """
    try:
        from git.exc import InvalidGitRepositoryError
        from git.repo.base import Repo
    except ImportError:
        return None

    try:
        repo = Repo(search_parent_directories=True)
    except InvalidGitRepositoryError:
        return None

    if clean and repo.is_dirty(untracked_files=True):
        return None
    return cast(str, repo.head.object.hexsha)


class PipelineModel(AnalyticsTrackedModelMixin):
    """Pydantic object representing a pipeline.

    Attributes:
        name: Pipeline name
        docstring: Docstring of the pipeline
        steps: List of steps in this pipeline
    """

    ANALYTICS_FIELDS: ClassVar[List[str]] = ["id", "project", "user"]

    id: Optional[UUID]
    name: str

    project: Optional[UUID] = Field(
        default=None,
        title="The project that contains this component."
    )
    user: Optional[UUID] = Field(
        default=None,
        title="The id of the user that owns this component.",
    )

    docstring: Optional[str]
    configuration: Dict[str, str]

    creation_date: Optional[datetime] = Field(
        default=None,
        title="The time at which the component was registered.",
    )

    def to_hydrated_model(self) -> "HydratedPipelineModel":
        zen_store = GlobalConfiguration().zen_store

        project = zen_store.get_project(self.project)
        user = zen_store.get_user(self.user)

        return HydratedPipelineModel(id=self.id,
                                     name=self.name,
                                     project=project,
                                     user=user,
                                     docstring=self.docstring,
                                     configuration=self.configuration,
                                     creation_date=self.creation_date)


class HydratedPipelineModel(PipelineModel):
    """Network Serializable Model describing the Component with User and Project
     fully hydrated.
    """
    project: ProjectModel = Field(
        default=None, title="The project that contains this stack."
    )
    user: UserModel = Field(
        default=None,
        title="The id of the user, that created this stack.",
    )


class PipelineRunModel(BaseModel):
    """Pydantic object representing a pipeline run.

    Attributes:
        name: Pipeline run name.
        zenml_version: Version of ZenML that this pipeline run was performed
            with.
        git_sha: Git commit SHA that this pipeline run was performed on. This
            will only be set if the pipeline code is in a git repository and
            there are no uncommitted files when running the pipeline.
        pipeline: Pipeline that this run is referring to.
        stack: Stack that this run was performed on.
        runtime_configuration: Runtime configuration that was used for this run.
        owner: Id of the user that ran this pipeline.
    """

    id: Optional[UUID]
    name: str

    owner: Optional[UUID]  # might not be set for scheduled runs
    stack_id: Optional[UUID]  # might not be set for scheduled runs
    pipeline_id: Optional[UUID]  # might not be set for scheduled runs

    runtime_configuration: Optional[Dict[str, Any]]

    zenml_version: Optional[str] = current_zenml_version
    git_sha: Optional[str] = Field(default_factory=get_git_sha)
    created_at: Optional[datetime]

    # ID in MLMD - needed for some metadata store methods
    mlmd_id: Optional[int]


class StepRunModel(BaseModel):
    """Pydantic object representing a step of a pipeline run."""

    id: Optional[UUID]
    name: str

    pipeline_run_id: Optional[UUID]
    parent_step_ids: Optional[List[UUID]]

    docstring: Optional[str]
    parameters: Dict[str, str]
    entrypoint_name: str

    # IDs in MLMD - needed for some metadata store methods
    mlmd_id: int
    mlmd_parent_step_ids: List[int]


class ArtifactModel(BaseModel):
    """Pydantic object representing an artifact."""

    id: Optional[UUID]
    name: Optional[str]  # Name of the output in the parent step

    parent_step_id: Optional[UUID]
    producer_step_id: Optional[UUID]

    type: ArtifactType
    uri: str
    materializer: str
    data_type: str
    is_cached: bool

    # IDs in MLMD - needed for some metadata store methods
    mlmd_id: int
    mlmd_parent_step_id: int
    mlmd_producer_step_id: int
