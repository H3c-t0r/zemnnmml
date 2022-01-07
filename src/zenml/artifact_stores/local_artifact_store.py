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

from pydantic import validator

from zenml.artifact_stores import BaseArtifactStore
from zenml.constants import REMOTE_FS_PREFIX


class LocalArtifactStore(BaseArtifactStore):
    """Artifact Store for local artifacts."""

    @validator("path")
    def must_be_local_path(cls, v: str) -> str:
        """Validates that the path is a local path."""
        if any([v.startswith(prefix) for prefix in REMOTE_FS_PREFIX]):
            raise ValueError("Must be a local path.")
        return v
