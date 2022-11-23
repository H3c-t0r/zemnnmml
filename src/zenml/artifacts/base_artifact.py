# Copyright 2019 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
"""Base class for ZenML artifacts."""
from typing import Any


class BaseArtifact:
    """Base class for all ZenML artifacts.

    Every implementation of an artifact needs to inherit from this class and be
    given a unique TYPE_NAME.
    """

    TYPE_NAME: str = "BaseArtifact"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init method for BaseArtifact.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.
        """
        self.set_zenml_artifact_type()
        self.name = None
        self.uri = None
        self.materializer = None
        self.data_type = None

    @classmethod
    def set_zenml_artifact_type(cls) -> None:
        """Set the type of the artifact.

        Raises:
            ValueError: If the artifact type is not a string or dictionary.
        """
        type_name = cls.TYPE_NAME
        if not (type_name and isinstance(type_name, str)):
            raise ValueError(
                (
                    "The Artifact subclass %s must override the TYPE_NAME attribute "
                    "with a string type name identifier (got %r instead)."
                )
                % (cls, type_name)
            )
