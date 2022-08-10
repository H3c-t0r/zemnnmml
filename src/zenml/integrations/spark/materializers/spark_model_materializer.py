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

import os
from typing import Any, Type, Union

from pyspark.ml import Estimator, Transformer

from zenml.artifacts.model_artifact import ModelArtifact
from zenml.materializers.base_materializer import BaseMaterializer

DEFAULT_FILEPATH = "model"


class SparkModelMaterializer(BaseMaterializer):
    """Materializer to read/write NeuralProphet models."""

    ASSOCIATED_TYPES = (Transformer, Estimator)
    ASSOCIATED_ARTIFACT_TYPES = (ModelArtifact,)

    def handle_input(
        self, model_type: Type[Any]
    ) -> Union[Transformer, Estimator]:
        """Reads and returns a Spark ML model.

        Returns:
            A loaded spark model.
        """
        super().handle_input(model_type)
        path = os.path.join(self.artifact.uri, DEFAULT_FILEPATH)
        return model_type.load(path)  # noqa

    def handle_return(self, model: Union[Transformer, Estimator]) -> None:
        """Writes a spark model.

        Args:
            model: A spark model.
        """
        super().handle_return(model)

        # Write the dataframe to the artifact store
        path = os.path.join(self.artifact.uri, DEFAULT_FILEPATH)
        model.save(path)
