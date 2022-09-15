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
"""Model definitions for code projects."""

from datetime import datetime
from typing import ClassVar, List, Optional
from uuid import UUID, uuid4

from pydantic import Field

from zenml.utils.analytics_utils import AnalyticsTrackedModelMixin


class ProjectModel(AnalyticsTrackedModelMixin):
    """Domain Model describing the Project."""

    ANALYTICS_FIELDS: ClassVar[List[str]] = [
        "id",
    ]

    id: UUID = Field(default_factory=uuid4, title="The unique if of the stack.")
    name: str = Field(title="The unique name of the stack.")
    description: Optional[str] = Field(
        default=None, title="The description of the project.", max_length=300
    )
    creation_date: datetime = Field(
        default_factory=datetime.now,
        title="The time at which the project was created.",
    )
