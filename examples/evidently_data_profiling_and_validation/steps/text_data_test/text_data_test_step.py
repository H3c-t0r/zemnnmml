#  Copyright (c) ZenML GmbH 2023. All Rights Reserved.
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
from zenml.integrations.evidently.steps import (
    EvidentlyColumnMapping,
    EvidentlyTestParameters,
    evidently_test_step,
)

text_data_test = evidently_test_step(
    step_name="text_data_test",
    params=EvidentlyTestParameters(
        column_mapping=EvidentlyColumnMapping(
            target="Rating",
            numerical_features=["Age", "Positive_Feedback_Count"],
            categorical_features=[
                "Division_Name",
                "Department_Name",
                "Class_Name",
            ],
            text_features=["Review_Text", "Title"],
            prediction="class",
        ),
        tests=[
            "DataQualityTestPreset",
            {
                "test": "TestColumnRegExp",
                "parameters": {"reg_exp": "^[0..9]"},
                "columns": ["Review_Text", "Title"],
            },
        ],
    ),
)
