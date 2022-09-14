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
"""Model definitions for users, teams, and roles."""

from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, root_validator

from zenml.utils.analytics_utils import AnalyticsTrackedModelMixin


class RoleModel(AnalyticsTrackedModelMixin):
    """Pydantic object representing a role.

    Attributes:
        id: Id of the role.
        created_at: Date when the role was created.
        name: Name of the role.
        permissions: Set of permissions allowed by this role.
    """

    ANALYTICS_FIELDS: ClassVar[List[str]] = ["id"]

    id: Optional[UUID] = None
    name: str
    created_at: Optional[datetime] = None


class UserModel(AnalyticsTrackedModelMixin):
    """Pydantic object representing a user.

    Attributes:
        id: Id of the user.
        created_at: Date when the user was created.
        name: Name of the user.
    """

    ANALYTICS_FIELDS: ClassVar[List[str]] = ["id"]

    id: Optional[UUID] = None
    name: str
    created_at: Optional[datetime] = None
    # email: str
    # password: str


class TeamModel(AnalyticsTrackedModelMixin):
    """Pydantic object representing a team.

    Attributes:
        id: Id of the team.
        created_at: Date when the team was created.
        name: Name of the team.
    """

    ANALYTICS_FIELDS: ClassVar[List[str]] = ["id"]

    id: Optional[UUID] = None
    name: str
    created_at: Optional[datetime] = None


class RoleAssignmentModel(BaseModel):
    """Pydantic object representing a role assignment.

    Attributes:
        id: Id of the role assignment.
        role_id: Id of the role.
        project_id: Optional ID of a project that the role is limited to.
        team_id: Id of a team to which the role is assigned.
        user_id: Id of a user to which the role is assigned.
        created_at: Date when the role was assigned.
    """

    id: Optional[UUID] = None
    role_id: UUID
    project_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

    @root_validator
    def ensure_single_entity(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validates that either `user_id` or `team_id` is set.

        Args:
            values: The values to validate.

        Returns:
            The validated values.

        Raises:
            ValueError: If neither `user_id` nor `team_id` is set.
        """
        user_id = values.get("user_id", None)
        team_id = values.get("team_id", None)
        if user_id and team_id:
            raise ValueError("Only `user_id` or `team_id` is allowed.")

        if not (user_id or team_id):
            raise ValueError(
                "Missing `user_id` or `team_id` for role assignment."
            )

        return values
