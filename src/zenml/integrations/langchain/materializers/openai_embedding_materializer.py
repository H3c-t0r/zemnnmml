#  Copyright (c) ZenML GmbH 2023. All Rights Reserved.
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
"""Implementation of the langchain openai embedding materializer."""


import os
import pickle
from typing import Type, cast

from langchain.embeddings import OpenAIEmbeddings

from zenml.enums import ArtifactType
from zenml.io import fileio
from zenml.materializers.base_materializer import BaseMaterializer

DEFAULT_FILENAME = "embedding.pkl"


class LangchainOpenaiEmbeddingMaterializer(BaseMaterializer):
    """Handle langchain openai embedding objects."""

    ASSOCIATED_ARTIFACT_TYPE = ArtifactType.MODEL
    ASSOCIATED_TYPES = (OpenAIEmbeddings,)

    def load(self, data_type: Type[OpenAIEmbeddings]) -> OpenAIEmbeddings:
        """Reads a openai embedding from a pickle file.

        Args:
            data_type: The type of the vector store.

        Returns:
            The vector store.
        """
        super().load(data_type)
        filepath = os.path.join(self.uri, DEFAULT_FILENAME)
        with fileio.open(filepath, "rb") as fid:
            embedding = pickle.load(fid)
        return cast(OpenAIEmbeddings, embedding)

    def save(self, embedding: OpenAIEmbeddings) -> None:
        """Save an OpenAI embedding as a pickle file.

        Args:
            embedding: The embedding to save.
        """
        super().save(embedding)
        filepath = os.path.join(self.uri, DEFAULT_FILENAME)
        with fileio.open(filepath, "wb") as fid:
            pickle.dump(embedding, fid)
