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

from pipelines.fashion_mnist_pipeline import fashion_mnist_pipeline

if __name__ == "__main__":
    fashion_mnist_pipeline()

    # In case you want to run this on a schedule uncomment the following lines.
    # Note that Airflow schedules need to be set in the past:

    # from datetime import datetime, timedelta

    # from zenml.pipelines import Schedule

    # scheduled_pipeline = fashion_mnist_pipeline.with_options(
    #     schedule=Schedule(
    #         start_time=datetime.now() - timedelta(hours=1),
    #         end_time=datetime.now() + timedelta(hours=1),
    #         interval_second=timedelta(minutes=15),
    #         catchup=False,
    #     )
    # )
    # scheduled_pipeline()
