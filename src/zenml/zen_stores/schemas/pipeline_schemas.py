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
"""SQL Model Implementations for Pipelines and Pipeline Runs."""

import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from zenml.enums import ArtifactType
from zenml.models import PipelineModel, PipelineRunModel
from zenml.models.pipeline_models import ArtifactModel, StepRunModel


class PipelineSchema(SQLModel, table=True):
    """SQL Model for pipelines."""

    id: UUID = Field(primary_key=True)

    name: str

    project: UUID = Field(foreign_key="projectschema.id")
    user: UUID = Field(foreign_key="userschema.id")

    docstring: Optional[str] = Field(nullable=True)
    configuration: str

    creation_date: datetime

    runs: List["PipelineRunSchema"] = Relationship(
        back_populates="pipeline",
    )

    @classmethod
    def from_create_model(cls, pipeline: PipelineModel) -> "PipelineSchema":
        """Create a `PipelineSchema` from a `PipelineModel`.

        Args:
            pipeline: The `PipelineModel` to create the schema from.

        Returns:
            The created `PipelineSchema`.
        """
        return cls(
            id=pipeline.id,
            creation_date=pipeline.creation_date,
            name=pipeline.name,
            project_id=pipeline.project,
            user=pipeline.user,
            docstring=pipeline.docstring,
            configuration=json.dumps(pipeline.configuration),
        )

    def from_update_model(self, model: PipelineModel) -> "PipelineSchema":
        """Update a `PipelineSchema` from a PipelineModel.

        Args:
            model: The `PipelineModel` to update the schema from.

        Returns:
            The updated `PipelineSchema`.
        """
        self.name = model.name
        self.docstring = model.docstring
        return self

    def to_model(self) -> "PipelineModel":
        """Convert a `PipelineSchema` to a `PipelineModel`.

        Returns:
            The created PipelineModel.
        """
        return PipelineModel(
            id=self.id,
            name=self.name,
            project=self.project,
            user=self.user,
            docstring=self.docstring,
            configuration=json.loads(self.configuration),
            creation_date=self.creation_date,
        )


class PipelineRunSchema(SQLModel, table=True):
    """SQL Model for pipeline runs."""

    id: UUID = Field(primary_key=True)
    name: str

    # project_id - redundant since stack has this
    user: Optional[UUID] = Field(foreign_key="userschema.id", nullable=True)
    stack_id: Optional[UUID] = Field(
        foreign_key="stackschema.id", nullable=True
    )
    pipeline_id: Optional[UUID] = Field(
        foreign_key="pipelineschema.id", nullable=True
    )

    runtime_configuration: Optional[str] = Field(nullable=True)
    git_sha: Optional[str] = Field(nullable=True)
    zenml_version: str

    creation_date: datetime

    pipeline: PipelineSchema = Relationship(back_populates="runs")

    mlmd_id: int = Field(default=None, nullable=True)

    @classmethod
    def from_create_model(
        cls,
        run: PipelineRunModel,
        pipeline: Optional[PipelineSchema] = None,
    ) -> "PipelineRunSchema":
        """Create a `PipelineRunSchema` from a `PipelineRunModel`.

        Args:
            run: The `PipelineRunModel` to create the schema from.
            pipeline: The `PipelineSchema` to link to the run.

        Returns:
            The created `PipelineRunSchema`.
        """
        return cls(
            id=run.id,
            creation_date=run.creation_date,
            name=run.name,
            stack_id=run.stack_id,
            user=run.user,
            pipeline_id=run.pipeline_id,
            runtime_configuration=json.dumps(run.runtime_configuration),
            git_sha=run.git_sha,
            zenml_version=run.zenml_version,
            pipeline=pipeline,
            mlmd_id=run.mlmd_id,
        )

    def from_update_model(self, model: PipelineRunModel) -> "PipelineRunSchema":
        """Update a `PipelineRunSchema` from a `PipelineRunModel`.

        Args:
            model: The `PipelineRunModel` to update the schema from.

        Returns:
            The updated `PipelineRunSchema`.
        """
        self.name = model.name
        self.runtime_configuration = json.dumps(model.runtime_configuration)
        self.git_sha = model.git_sha
        assert model.zenml_version is not None
        self.zenml_version = model.zenml_version
        assert model.mlmd_id is not None
        self.mlmd_id = model.mlmd_id
        return self

    def to_model(self) -> PipelineRunModel:
        """Convert a `PipelineRunSchema` to a `PipelineRunModel`.

        Returns:
            The created `PipelineRunModel`.
        """
        config = self.runtime_configuration
        if config is not None:
            config = json.loads(config)
        return PipelineRunModel(
            id=self.id,
            name=self.name,
            stack_id=self.stack_id,
            user=self.user,
            pipeline_id=self.pipeline_id,
            runtime_configuration=config,
            git_sha=self.git_sha,
            zenml_version=self.zenml_version,
            creation_date=self.creation_date,
            mlmd_id=self.mlmd_id,
        )


class StepRunSchema(SQLModel, table=True):
    """SQL Model for steps of pipeline runs."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str

    pipeline_run_id: UUID = Field(foreign_key="pipelinerunschema.id")

    docstring: Optional[str]
    parameters: str
    entrypoint_name: str

    mlmd_id: int = Field(default=None, nullable=True)

    @classmethod
    def from_create_model(cls, model: StepRunModel) -> "StepRunSchema":
        """Create a `StepRunSchema` from a `StepRunModel`.

        Args:
            model: The `StepRunModel` to create the schema from.

        Returns:
            The created `StepRunSchema`.

        """
        return cls(
            name=model.name,
            pipeline_run_id=model.pipeline_run_id,
            docstring=model.docstring,
            parameters=json.dumps(model.parameters),
            entrypoint_name=model.entrypoint_name,
            mlmd_id=model.mlmd_id,
        )

    def to_model(
        self, parent_step_ids: List[UUID], mlmd_parent_step_ids: List[int]
    ) -> StepRunModel:
        """Convert a `StepRunSchema` to a `StepRunModel`.

        Args:
            parent_step_ids: The parent step ids to link to the step.
            mlmd_parent_step_ids: The parent step ids in MLMD.

        Returns:
            The created StepRunModel.
        """
        return StepRunModel(
            id=self.id,
            name=self.name,
            pipeline_run_id=self.pipeline_run_id,
            parent_step_ids=parent_step_ids,
            docstring=self.docstring,
            parameters=json.loads(self.parameters),
            entrypoint_name=self.entrypoint_name,
            mlmd_id=self.mlmd_id,
            mlmd_parent_step_ids=mlmd_parent_step_ids,
        )


class StepRunOrderSchema(SQLModel, table=True):
    """SQL Model that defines the order of steps."""

    parent_id: UUID = Field(foreign_key="steprunschema.id", primary_key=True)
    child_id: UUID = Field(foreign_key="steprunschema.id", primary_key=True)


class ArtifactSchema(SQLModel, table=True):
    """SQL Model for artifacts of steps."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str  # Name of the output in the parent step

    parent_step_id: UUID = Field(foreign_key="steprunschema.id")
    producer_step_id: UUID = Field(foreign_key="steprunschema.id")

    type: ArtifactType
    uri: str
    materializer: str
    data_type: str
    is_cached: bool

    mlmd_id: int = Field(default=None, nullable=True)
    mlmd_parent_step_id: int = Field(default=None, nullable=True)
    mlmd_producer_step_id: int = Field(default=None, nullable=True)

    @classmethod
    def from_create_model(cls, model: ArtifactModel) -> "ArtifactSchema":
        """Create an `ArtifactSchema` from an `ArtifactModel`.

        Args:
            model: The `ArtifactModel` to create the schema from.

        Returns:
            The created `ArtifactSchema`.
        """
        return cls(
            name=model.name,
            parent_step_id=model.parent_step_id,
            producer_step_id=model.producer_step_id,
            type=model.type,
            uri=model.uri,
            materializer=model.materializer,
            data_type=model.data_type,
            is_cached=model.is_cached,
            mlmd_id=model.mlmd_id,
            mlmd_parent_step_id=model.mlmd_parent_step_id,
            mlmd_producer_step_id=model.mlmd_producer_step_id,
        )

    def to_model(self) -> ArtifactModel:
        """Convert an `ArtifactSchema` to an `ArtifactModel`.

        Returns:
            The created `ArtifactModel`.
        """
        return ArtifactModel(
            id=self.id,
            name=self.name,
            parent_step_id=self.parent_step_id,
            producer_step_id=self.producer_step_id,
            type=self.type,
            uri=self.uri,
            materializer=self.materializer,
            data_type=self.data_type,
            is_cached=self.is_cached,
            mlmd_id=self.mlmd_id,
            mlmd_parent_step_id=self.mlmd_parent_step_id,
            mlmd_producer_step_id=self.mlmd_producer_step_id,
        )


class StepInputArtifactSchema(SQLModel, table=True):
    """SQL Model that defines which artifacts are inputs to which step."""

    step_id: UUID = Field(foreign_key="steprunschema.id", primary_key=True)
    artifact_id: UUID = Field(foreign_key="artifactschema.id", primary_key=True)
    name: str  # Name of the input in the step
