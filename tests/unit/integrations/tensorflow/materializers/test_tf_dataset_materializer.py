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

import pytest
import tensorflow as tf

from tests.unit.test_general import _test_materializer
from zenml.integrations.tensorflow.materializers.tf_dataset_materializer import (
    TensorflowDatasetMaterializer,
)


@pytest.mark.skip(reason="Tensorflow is too big to install on CI currently")
def test_tensorflow_tf_dataset_materializer(clean_client):
    """Tests whether the steps work for the TensorFlow TF Dataset materializer."""
    dataset = _test_materializer(
        step_output=tf.data.Dataset.from_tensor_slices([1, 2, 3]),
        step_output_type=tf.data.Dataset,
        materializer_class=TensorflowDatasetMaterializer,
        expected_metadata_size=2,
    )

    assert isinstance(dataset.element_spec.dtype, type(tf.int32))
