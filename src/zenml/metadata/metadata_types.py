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
"""Custom types that can be used as metadata of ZenML artifacts."""

from typing import Union

from zenml.utils.enum_utils import StrEnum


class Uri(str):
    """Special string class to indicate a URI."""


class Path(str):
    """Special string class to indicate a path."""


class DType(str):
    """Special string class to indicate a data type."""


def human_readable_size(num_bytes: int) -> str:
    """Converts a number of bytes to a human-readable string.

    Args:
        num_bytes: The number of bytes.

    Returns:
        A human-readable string representation of the data size.
    """
    for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]:
        if abs(num_bytes) < 1000:
            return f"{num_bytes}{unit}"
        num_bytes = num_bytes // 1000
    return f"{num_bytes}YB"


class StorageSize(int):
    """Storage size of an artifact in number of bytes."""


# Union of all types that can be used as metadata.
# We don't use subscripted generics here because they cannot be used for
# `isinstance` checks.
MetadataType = Union[
    str,
    int,
    float,
    bool,
    dict,
    list,
    set,
    tuple,  # type: ignore[type-arg]
    Uri,
    Path,
    DType,
    StorageSize,
]


class MetadataTypeEnum(StrEnum):
    """String Enum of all possible types that metadata can have."""

    STRING = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"
    DICT = "dict"
    TUPLE = "tuple"
    SET = "set"
    URI = "Uri"
    PATH = "Path"
    DTYPE = "DType"
    STORAGE_SIZE = "StorageSize"


metadata_type_to_enum_mapping = {
    str: MetadataTypeEnum.STRING,
    int: MetadataTypeEnum.INT,
    float: MetadataTypeEnum.FLOAT,
    bool: MetadataTypeEnum.BOOL,
    dict: MetadataTypeEnum.DICT,
    list: MetadataTypeEnum.LIST,
    set: MetadataTypeEnum.SET,
    tuple: MetadataTypeEnum.TUPLE,
    Uri: MetadataTypeEnum.URI,
    Path: MetadataTypeEnum.PATH,
    DType: MetadataTypeEnum.DTYPE,
    StorageSize: MetadataTypeEnum.STORAGE_SIZE,
}

metadata_enum_to_type_mapping = {
    value: key for key, value in metadata_type_to_enum_mapping.items()
}


def get_metadata_type(
    object_: object,
) -> MetadataTypeEnum:
    """Get the metadata type enum for a given object.

    Args:
        object_: The object to get the metadata type for.

    Returns:
        The corresponding metadata type enum.

    Raises:
        ValueError: If the metadata type is not supported.
    """
    metadata_type = type(object_)
    if metadata_type in metadata_type_to_enum_mapping:
        return metadata_type_to_enum_mapping[metadata_type]
    raise ValueError(f"Metadata type {metadata_type} is not supported.")


def cast_to_metadata_type(
    value: object,
    type_: MetadataTypeEnum,
) -> MetadataType:
    """Cast an object to a metadata type.

    Args:
        value: The object to cast.
        type_: The metadata type to cast to.

    Returns:
        The value cast to the given metadata type.
    """
    metadata_type = metadata_enum_to_type_mapping[type_]
    typed_value = metadata_type(value)
    return typed_value  # type: ignore[no-any-return]
