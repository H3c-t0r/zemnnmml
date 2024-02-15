#  Copyright (c) ZenML GmbH 2024. All Rights Reserved.
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
"""Base implementation for all Plugin Flavors."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Generic, Type, TypeVar

from pydantic import BaseModel, Extra

from zenml.config.global_config import GlobalConfiguration
from zenml.enums import PluginSubType, PluginType
from zenml.models.v2.base.base_plugin_flavor import (
    BasePluginResponseBody,
    BasePluginResponseMetadata,
    BasePluginResponseResources,
)
from zenml.models import BasePluginFlavorResponse

if TYPE_CHECKING:
    from zenml.zen_stores.base_zen_store import BaseZenStore

AnyPluginResponse = TypeVar(
    "AnyPluginResponse",
    bound=BasePluginFlavorResponse[BasePluginResponseBody, BasePluginResponseMetadata, BasePluginResponseResources],
)


class BasePluginConfig(BaseModel, ABC):
    """Allows configuring of Event Source and Filter configuration."""

    class Config:
        """Pydantic configuration class."""

        # public attributes are immutable
        allow_mutation = True
        # all attributes with leading underscore are private and therefore
        # are mutable and not included in serialization
        underscore_attrs_are_private = True
        # ignore extra attributes during model initialization
        extra = Extra.ignore


class BasePlugin(ABC):
    """Base Class for all Plugins."""

    @property
    def zen_store(self) -> "BaseZenStore":
        """Returns the active zen store.

        Returns:
            The active zen store.
        """
        return GlobalConfiguration().zen_store

    @property
    @abstractmethod
    def config_class(self) -> Type[BasePluginConfig]:
        """Returns the `BasePluginConfig` config.

        Returns:
            The configuration.
        """


class BasePluginFlavor(ABC, Generic[AnyPluginResponse]):
    """Base Class for all PluginFlavors."""

    TYPE: ClassVar[PluginType]
    SUBTYPE: ClassVar[PluginSubType]
    FLAVOR: ClassVar[str]
    PLUGIN_CLASS: ClassVar[Type[BasePlugin]]

    @classmethod
    @abstractmethod
    def get_flavor_response_model(cls, hydrate: bool) -> BasePluginFlavorResponse[BasePluginResponseBody, BasePluginResponseMetadata, BasePluginResponseResources]:
        """Convert the Flavor into a Response Model.

        Args:
            hydrate: Whether the model should be hydrated.
        """
