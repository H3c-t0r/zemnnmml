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
"""Utility functions for handling tags."""

from typing import Union
from uuid import UUID

from zenml.utils.uuid_utils import generate_uuid_from_string


def _get_tag_resource_id(
    tag_id: Union[str, UUID], resource_id: Union[str, UUID]
) -> UUID:
    if isinstance(tag_id, str):
        tag_id = UUID(tag_id)
    if isinstance(resource_id, str):
        resource_id = UUID(resource_id)
    return generate_uuid_from_string(str(tag_id.hex) + str(resource_id.hex))
