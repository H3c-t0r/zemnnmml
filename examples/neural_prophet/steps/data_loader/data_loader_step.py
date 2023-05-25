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
import pandas as pd
from neuralprophet import NeuralProphet

from zenml import step
from zenml.steps import Output

DATA_LOCATION = "https://raw.githubusercontent.com/ourownstory/neuralprophet-data/main/datasets/"


@step
def data_loader() -> Output(df_train=pd.DataFrame, df_test=pd.DataFrame):
    """Return the renewable energy dataset as pandas dataframes."""
    sf_pv_df = pd.read_csv(DATA_LOCATION + "energy/SF_PV.csv")
    df_train, df_test = NeuralProphet().split_df(
        sf_pv_df, freq="H", valid_p=1.0 / 12
    )
    return df_train, df_test
