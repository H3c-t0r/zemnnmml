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
"""Neptune experiment tracker flavor"""

from typing import Type

from zenml.experiment_trackers.base_experiment_tracker import (
    BaseExperimentTrackerFlavor,
)
from zenml.integrations.neptune import NEPTUNE_MODEL_EXPERIMENT_TRACKER_FLAVOR
from zenml.integrations.neptune.experiment_trackers import (
    NeptuneExperimentTracker,
    NeptuneExperimentTrackerConfig,
)


class NeptuneExperimentTrackerFlavor(BaseExperimentTrackerFlavor):
    """Class for the `NeptuneExperimentTrackerFlavor`."""

    @property
    def name(self) -> str:
        """Name of the flavor.

        Returns:
            The name of the flavor.
        """
        return NEPTUNE_MODEL_EXPERIMENT_TRACKER_FLAVOR

    @property
    def config_class(self) -> Type[NeptuneExperimentTrackerConfig]:
        """Returns `NeptuneExperimentTrackerConfig` config class.

        Returns:
                The config class.
        """
        return NeptuneExperimentTrackerConfig

    @property
    def implementation_class(self) -> Type["NeptuneExperimentTracker"]:
        """Implementation class for this flavor.

        Returns:
            The implementation class.
        """
        from zenml.integrations.neptune.experiment_trackers import (
            NeptuneExperimentTracker,
        )

        return NeptuneExperimentTracker
