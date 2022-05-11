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
from typing import List, Optional, Sequence, Tuple

import pandas as pd


from zenml.artifacts import DataArtifact
from zenml.steps import Output
from zenml.steps.step_interfaces.base_drift_detection_step import (
    BaseAlerterConfig,
    BaseAlerterStep,
)

class SlackAlertConfig(BaseAlerterConfig):
    """TBD"""
    a: str = ""


class SlackAlerterStep(BaseAlerterStep):
    """TBD"""
    
    OUTPUT_SPEC = {
        "result": DataArtifact,
    }

    def entrypoint(  # type: ignore[override]
        self,
        message: str,
        config: SlackAlertConfig,
    ) -> bool:
        """Main entrypoint for the Evidently categorical target drift detection
        step.

        Args:
            

        Returns:
            
        """
        pass
