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
"""Metaclass implementation for registering ZenML BaseMaterializer subclasses."""

import inspect
from typing import Any, ClassVar, Dict, Tuple, Type, cast

from zenml.enums import ArtifactType
from zenml.exceptions import MaterializerInterfaceError
from zenml.io import fileio
from zenml.logger import get_logger
from zenml.materializers.materializer_registry import materializer_registry
from zenml.metadata.metadata_types import MetadataType

logger = get_logger(__name__)


class BaseMaterializerMeta(type):
    """Metaclass responsible for registering different BaseMaterializer subclasses.

    Materializers are used for reading/writing artifacts.
    """

    def __new__(
        mcs, name: str, bases: Tuple[Type[Any], ...], dct: Dict[str, Any]
    ) -> "BaseMaterializerMeta":
        """Creates a Materializer class and registers it at the `MaterializerRegistry`.

        Args:
            name: The name of the class.
            bases: The base classes of the class.
            dct: The dictionary of the class.

        Returns:
            The BaseMaterializerMeta class.

        Raises:
            MaterializerInterfaceError: If the class was improperly defined.
        """
        cls = cast(
            Type["BaseMaterializer"], super().__new__(mcs, name, bases, dct)
        )

        # Skip the following validation and registration for base classes.
        if cls.SKIP_REGISTRATION:
            # Reset the flag so subclasses don't have it set automatically.
            cls.SKIP_REGISTRATION = False
            return cls

        # Validate that the class is properly defined.
        if not cls.ASSOCIATED_TYPES:
            raise MaterializerInterfaceError(
                f"Invalid materializer class '{name}'. When creating a "
                f"custom materializer, make sure to specify at least one "
                f"type in its ASSOCIATED_TYPES class variable.",
                url="https://docs.zenml.io/advanced-guide/pipelines/materializers",
            )

        # Validate associated artifact type.
        if cls.ASSOCIATED_ARTIFACT_TYPE:
            try:
                cls.ASSOCIATED_ARTIFACT_TYPE = ArtifactType(
                    cls.ASSOCIATED_ARTIFACT_TYPE
                )
            except ValueError:
                raise MaterializerInterfaceError(
                    f"Invalid materializer class '{name}'. When creating a "
                    f"custom materializer, make sure to specify a valid "
                    f"artifact type in its ASSOCIATED_ARTIFACT_TYPE class "
                    f"variable.",
                    url="https://docs.zenml.io/advanced-guide/pipelines/materializers",
                )

        # Validate associated data types.
        for associated_type in cls.ASSOCIATED_TYPES:
            if not inspect.isclass(associated_type):
                raise MaterializerInterfaceError(
                    f"Associated type {associated_type} for materializer "
                    f"{name} is not a class.",
                    url="https://docs.zenml.io/advanced-guide/pipelines/materializers",
                )

        # Register the materializer.
        for associated_type in cls.ASSOCIATED_TYPES:
            materializer_registry.register_materializer_type(
                associated_type, cls
            )

        return cls


class BaseMaterializer(metaclass=BaseMaterializerMeta):
    """Base Materializer to realize artifact data."""

    ASSOCIATED_ARTIFACT_TYPE: ClassVar[ArtifactType] = ArtifactType.BASE
    ASSOCIATED_TYPES: ClassVar[Tuple[Type[Any], ...]] = ()

    # `SKIP_REGISTRATION` can be set to True to not register the class in the
    # materializer registry. This is primarily useful for defining base classes.
    # Subclasses will automatically have this set to False unless they override
    # it themselves.
    SKIP_REGISTRATION: ClassVar[bool] = True

    def __init__(self, uri: str):
        """Initializes a materializer with the given URI.

        Args:
            uri: The URI where the artifact data will be stored.
        """
        self.uri = uri

    # ================
    # Public Interface
    # ================

    def load(self, data_type: Type[Any]) -> Any:
        """Write logic here to load the data of an artifact.

        Args:
            data_type: What type the artifact data should be loaded as.

        Returns:
            The data of the artifact.
        """
        # read from a location inside self.uri
        return None

    def save(self, data: Any) -> None:
        """Write logic here to save the data of an artifact.

        Args:
            data: The data of the artifact to save.
        """
        # write `data` into self.uri

    def extract_metadata(self, data: Any) -> Dict[str, "MetadataType"]:
        """Extract metadata from the given data.

        This metadata will be tracked and displayed alongside the artifact.

        Args:
            data: The data to extract metadata from.

        Returns:
            A dictionary of metadata.
        """
        # Optionally, extract some metadata from `data` for ZenML to store.
        # E.g.:
        # return {
        #     "some_attribute_i_want_to_track": self.some_attribute,
        #     "pi": 3.14,
        # }
        return {}

    # ================
    # Internal Methods
    # ================

    def validate_type_compatibility(self, data_type: Type[Any]) -> None:
        """Checks whether the materializer can read/write the given type.

        Args:
            data_type: The type to check.

        Raises:
            TypeError: If the materializer cannot read/write the given type.
        """
        if not self._can_handle_type(data_type):
            raise TypeError(
                f"Unable to handle type {data_type}. {self.__class__.__name__} "
                f"can only read/write artifacts of the following types: "
                f"{self.ASSOCIATED_TYPES}."
            )

    def _can_handle_type(self, data_type: Type[Any]) -> bool:
        """Whether the materializer can read/write a certain type.

        Args:
            data_type: The type to check.

        Returns:
            Whether the materializer can read/write the given type.
        """
        return any(
            issubclass(data_type, associated_type)
            for associated_type in self.ASSOCIATED_TYPES
        )

    def extract_full_metadata(self, data: Any) -> Dict[str, "MetadataType"]:
        """Extract both base and custom metadata from the given data.

        Args:
            data: The data to extract metadata from.

        Returns:
            A dictionary of metadata.
        """
        base_metadata = self._extract_base_metadata(data)
        custom_metadata = self.extract_metadata(data)
        return {**base_metadata, **custom_metadata}

    def _extract_base_metadata(self, data: Any) -> Dict[str, "MetadataType"]:
        """Extract metadata from the given data.

        This metadata will be extracted for all artifacts in addition to the
        metadata extracted by the `extract_metadata` method.

        Args:
            data: The data to extract metadata from.

        Returns:
            A dictionary of metadata.
        """
        from zenml.metadata.metadata_types import StorageSize

        storage_size = fileio.size(self.uri)
        if isinstance(storage_size, int):
            return {"storage_size": StorageSize(storage_size)}
        return {}
