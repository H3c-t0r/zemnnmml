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
"""SQL Model Implementations."""
import base64
import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

from zenml.enums import StackComponentType
from zenml.models.code_models import CodeRepositoryModel
from zenml.models.component_models import ComponentModel
from zenml.models.pipeline_models import PipelineModel, PipelineRunModel
from zenml.models.stack_model import StackModel
from zenml.models.user_management_models import (
    ProjectModel,
    RoleAssignmentModel,
    RoleModel,
    TeamModel,
    UserModel,
)

# Projects, Repositories


class ProjectSchema(SQLModel, table=True):
    """SQL Model for projects."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str
    description: Optional[str] = Field(nullable=True)
    created_at: datetime = Field(default_factory=datetime.now)

    user_role_assignments: List["UserRoleAssignmentSchema"] = Relationship(
        back_populates="project", sa_relationship_kwargs={"cascade": "delete"}
    )
    team_role_assignments: List["TeamRoleAssignmentSchema"] = Relationship(
        back_populates="project", sa_relationship_kwargs={"cascade": "delete"}
    )

    @classmethod
    def from_create_model(cls, model: ProjectModel) -> "ProjectSchema":
        return cls(name=model.name, description=model.description)

    def from_update_model(self, model: ProjectModel) -> "ProjectSchema":
        self.name = model.name
        self.description = model.description
        return self

    def to_model(self) -> ProjectModel:
        return ProjectModel(
            id=self.id,
            name=self.name,
            description=self.description,
            created_at=self.created_at,
        )


class CodeRepositorySchema(SQLModel, table=True):
    """SQL Model for code repositories."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str
    project_id: UUID = Field(foreign_key="projectschema.id")
    created_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_create_model(
        cls, model: CodeRepositoryModel, project_id: UUID
    ) -> "CodeRepositorySchema":
        return cls(name=model.name, project_id=project_id)

    def from_update_model(
        self, model: CodeRepositoryModel
    ) -> "CodeRepositorySchema":
        self.name = model.name
        return self

    def to_model(self) -> CodeRepositoryModel:
        return CodeRepositoryModel(
            id=self.id,
            name=self.name,
            project_id=self.project_id,
            created_at=self.created_at,
        )


# Users, Teams, Roles


class TeamAssignmentSchema(SQLModel, table=True):
    """SQL Model for team assignments."""

    user_id: UUID = Field(primary_key=True, foreign_key="userschema.id")
    team_id: UUID = Field(primary_key=True, foreign_key="teamschema.id")


class UserSchema(SQLModel, table=True):
    """SQL Model for users."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str
    created_at: datetime = Field(default_factory=datetime.now)

    teams: List["TeamSchema"] = Relationship(
        back_populates="users", link_model=TeamAssignmentSchema
    )
    assigned_roles: List["UserRoleAssignmentSchema"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "delete"}
    )

    @classmethod
    def from_create_model(cls, model: UserModel) -> "UserSchema":
        return cls(name=model.name)

    def from_update_model(self, model: UserModel) -> "UserSchema":
        self.name = model.name
        return self

    def to_model(self) -> UserModel:
        return UserModel(id=self.id, name=self.name, created_at=self.created_at)


class TeamSchema(SQLModel, table=True):
    """SQL Model for teams."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str
    created_at: datetime = Field(default_factory=datetime.now)

    users: List["UserSchema"] = Relationship(
        back_populates="teams", link_model=TeamAssignmentSchema
    )
    assigned_roles: List["TeamRoleAssignmentSchema"] = Relationship(
        back_populates="team", sa_relationship_kwargs={"cascade": "delete"}
    )

    @classmethod
    def from_create_model(cls, model: TeamModel) -> "TeamSchema":
        return cls(name=model.name)

    def to_model(self) -> TeamModel:
        return TeamModel(id=self.id, name=self.name, created_at=self.created_at)


class RoleSchema(SQLModel, table=True):
    """SQL Model for roles."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str
    created_at: datetime = Field(default_factory=datetime.now)

    user_role_assignments: List["UserRoleAssignmentSchema"] = Relationship(
        back_populates="role", sa_relationship_kwargs={"cascade": "delete"}
    )
    team_role_assignments: List["TeamRoleAssignmentSchema"] = Relationship(
        back_populates="role", sa_relationship_kwargs={"cascade": "delete"}
    )

    @classmethod
    def from_create_model(cls, model: RoleModel) -> "RoleSchema":
        return cls(name=model.name)

    def to_model(self) -> RoleModel:
        return RoleModel(id=self.id, name=self.name, created_at=self.created_at)


class UserRoleAssignmentSchema(SQLModel, table=True):
    """SQL Model for assigning roles to users for a given project."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    role_id: UUID = Field(foreign_key="roleschema.id")
    user_id: UUID = Field(foreign_key="userschema.id")
    project_id: Optional[UUID] = Field(
        foreign_key="projectschema.id", nullable=True
    )
    created_at: datetime = Field(default_factory=datetime.now)

    role: RoleSchema = Relationship(back_populates="user_role_assignments")
    user: UserSchema = Relationship(back_populates="assigned_roles")
    project: Optional[ProjectSchema] = Relationship(
        back_populates="user_role_assignments"
    )

    def to_model(self) -> RoleAssignmentModel:
        return RoleAssignmentModel(
            id=self.id,
            role_id=self.role_id,
            user_id=self.user_id,
            project_id=self.project_id,
            created_at=self.created_at,
        )


class TeamRoleAssignmentSchema(SQLModel, table=True):
    """SQL Model for assigning roles to teams for a given project."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    role_id: UUID = Field(foreign_key="roleschema.id")
    team_id: UUID = Field(foreign_key="teamschema.id")
    project_id: Optional[UUID] = Field(
        foreign_key="projectschema.id", nullable=True
    )
    created_at: datetime = Field(default_factory=datetime.now)

    role: RoleSchema = Relationship(back_populates="team_role_assignments")
    team: TeamSchema = Relationship(back_populates="assigned_roles")
    project: Optional[ProjectSchema] = Relationship(
        back_populates="team_role_assignments"
    )

    def to_model(self) -> RoleAssignmentModel:
        return RoleAssignmentModel(
            id=self.id,
            role_id=self.role_id,
            team_id=self.team_id,
            project_id=self.project_id,
            created_at=self.created_at,
        )


# Stacks, Stack Components, Flavors


class FlavorSchema(SQLModel, table=True):
    """SQL Model for flavors."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)

    name: str

    # project_id - redundant since repository has this
    repository_id: UUID = Field(foreign_key="coderepositoryschema.id")
    created_by: UUID = Field(foreign_key="userschema.id")

    type: StackComponentType
    source: str
    git_sha: str
    integration: str

    created_at: datetime = Field(default_factory=datetime.now)


class StackCompositionSchema(SQLModel, table=True):
    """SQL Model for stack definitions.

    Join table between Stacks and StackComponents.
    """

    stack_id: UUID = Field(primary_key=True, foreign_key="stackschema.id")
    component_id: UUID = Field(
        primary_key=True, foreign_key="stackcomponentschema.id"
    )


class StackSchema(SQLModel, table=True):
    """SQL Model for stacks."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)

    name: str
    is_shared: bool
    project_id: UUID = Field(
        foreign_key="projectschema.id",
    )
    owner: UUID = Field(
        foreign_key="userschema.id",
    )

    components: List["StackComponentSchema"] = Relationship(
        back_populates="stacks", link_model=StackCompositionSchema
    )

    @classmethod
    def from_create_model(
        cls,
        user_id: UUID,
        project_id: UUID,
        defined_components: List["StackComponentSchema"],
        stack: StackModel,
    ) -> "StackSchema":
        """Create an incomplete StackSchema with `id` and `created_at` missing.

        Returns:
            A StackSchema
        """

        return cls(
            name=stack.name,
            project_id=project_id,
            owner=user_id,
            is_shared=stack.is_shared,
            components=defined_components,
        )

    def from_update_model(
        self,
        defined_components: List["StackComponentSchema"],
        stack: StackModel,
    ) -> "StackSchema":
        """Update the updatable fields on an existing StackSchema.

        Returns:
            A StackSchema
        """
        self.name = stack.name
        self.is_shared = stack.is_shared
        self.components = defined_components
        return self

    def to_model(self) -> "StackModel":
        """Creates a ComponentModel from an instance of a StackSchema.

        Returns:
            a StackModel
        """
        return StackModel(
            id=self.id,
            name=self.name,
            owner=self.owner,
            project_id=self.project_id,
            is_shared=self.is_shared,
            components={c.type: c.to_model() for c in self.components},
        )


class StackComponentSchema(SQLModel, table=True):
    """SQL Model for stack components."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)

    name: str
    is_shared: bool

    type: StackComponentType
    flavor_name: str
    # flavor_id: UUID = Field(foreign_key="flavorschema.id", nullable=True)
    # TODO: Prefill flavors
    owner: UUID = Field(foreign_key="userschema.id")
    project_id: UUID = Field(foreign_key="projectschema.id")

    configuration: bytes

    created_at: datetime = Field(default_factory=datetime.now)

    stacks: List["StackSchema"] = Relationship(
        back_populates="components", link_model=StackCompositionSchema
    )

    @classmethod
    def from_create_model(
        cls, user_id: str, project_id: UUID, component: ComponentModel
    ) -> "StackComponentSchema":
        """Create a StackComponentSchema with `id` and `created_at` missing.


        Returns:
            A StackComponentSchema
        """
        return cls(
            name=component.name,
            project_id=project_id,
            owner=user_id,
            is_shared=component.is_shared,
            type=component.type,
            flavor_name=component.flavor_name,
            configuration=base64.b64encode(
                json.dumps(component.configuration).encode("utf-8")
            ),
        )

    def from_update_model(
        self,
        component: ComponentModel,
    ) -> "StackComponentSchema":
        """Update the updatable fields on an existing StackSchema.

        Returns:
            A StackSchema
        """
        self.name = component.name
        self.is_shared = component.is_shared
        self.configuration = base64.b64encode(
            json.dumps(component.configuration).encode("utf-8")
        )
        return self

    def to_model(self) -> "ComponentModel":
        """Creates a ComponentModel from an instance of a StackSchema.

        Returns:
            A ComponentModel
        """
        return ComponentModel(
            id=self.id,
            name=self.name,
            type=self.type,
            flavor_name=self.flavor_name,
            owner=self.owner,
            project_id=self.project_id,
            is_shared=self.is_shared,
            configuration=json.loads(
                base64.b64decode(self.configuration).decode()
            ),
        )


# Pipelines, Steps, Runs


class PipelineSchema(SQLModel, table=True):
    """SQL Model for pipelines."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)

    name: str

    project_id: UUID = Field(foreign_key="projectschema.id")
    # repository_id: UUID = Field(foreign_key="coderepositoryschema.id")
    owner: UUID = Field(foreign_key="userschema.id")

    docstring: str  # TODO: how to get this?
    # configuration: str

    created_at: datetime = Field(default_factory=datetime.now)

    # runs = Relationship(
    #     back_populates="pipeline",
    # )

    @classmethod
    def from_create_model(cls, model: PipelineModel) -> "PipelineSchema":
        pass  # TODO

    def from_update_model(self, model: PipelineModel) -> "PipelineSchema":
        self.name = model.name
        self.docstring = model.docstring
        # self.configuration = model.configuration
        return self

    def to_model(self) -> "PipelineModel":
        pass  # TODO


class PipelineRunSchema(SQLModel, table=True):
    """SQL Model for pipeline runs."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    mlmd_id: int = Field(default=None, nullable=True)
    name: str

    # project_id - redundant since stack has this
    owner: UUID = Field(foreign_key="userschema.id")
    stack_id: UUID = Field(foreign_key="stackschema.id")
    pipeline_id: Optional[UUID] = Field(
        foreign_key="pipelineschema.id", nullable=True
    )

    runtime_configuration: str
    git_sha: Optional[str] = Field(nullable=True)
    zenml_version: str

    created_at: datetime = Field(default_factory=datetime.now)

    # pipeline: PipelineSchema = Relationship(back_populates="runs")

    @classmethod
    def from_create_model(
        cls,
        model: PipelineRunModel,
        pipeline: Optional[PipelineSchema] = None,
    ) -> "PipelineRunSchema":
        return cls(
            mlmd_id=model.mlmd_id,
            name=model.name,
            stack_id=model.stack_id,
            owner=model.owner,
            pipeline_id=model.pipeline_id,
            runtime_configuration=json.dumps(model.runtime_configuration),
            git_sha=model.git_sha,
            zenml_version=model.zenml_version,
            pipeline=pipeline,
        )

    def from_update_model(self, model: PipelineRunModel) -> "PipelineRunSchema":
        self.mlmd_id = model.mlmd_id
        self.name = model.name
        self.runtime_configuration = json.dumps(model.runtime_configuration)
        self.git_sha = model.git_sha
        self.zenml_version = model.zenml_version
        return self

    def to_model(self) -> PipelineRunModel:
        return PipelineRunModel(
            id=self.id,
            mlmd_id=self.mlmd_id,
            name=self.name,
            stack_id=self.stack_id,
            owner=self.owner,
            pipeline_id=self.pipeline_id,
            runtime_configuration=json.loads(self.runtime_configuration),
            git_sha=self.git_sha,
            zenml_version=self.zenml_version,
            created_at=self.created_at,
        )


# MLMD


class MLMDSchema(SQLModel, table=True):
    """SQL Model for MLMD."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    project_id: UUID = Field(foreign_key="projectschema.id")
    type: str


class MLMDPropertySchema(SQLModel, table=True):
    """SQL Model for MLMD Properties."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str
    mlmd_id: UUID = Field(foreign_key="mlmdschema.id")
    value: str
