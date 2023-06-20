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
"""Implementation of the post-execution pipeline."""

from functools import partial
from typing import TYPE_CHECKING, Any, List, Optional, Type, Union

from zenml.client import Client
from zenml.logger import get_logger
from zenml.models import (
    PipelineResponseModel,
    PipelineRunResponseModel,
)
from zenml.utils.analytics_utils import AnalyticsEvent, track
from zenml.utils.pagination_utils import depaginate

if TYPE_CHECKING:
    from zenml.new.pipelines.pipeline import Pipeline

logger = get_logger(__name__)


@track(event=AnalyticsEvent.GET_PIPELINES)
def get_pipelines() -> List["PipelineResponseModel"]:
    """Fetches all post-execution pipeline views in the active workspace.

    Returns:
        A list of post-execution pipeline views.
    """
    logger.warning(
        "`zenml.post_execution.get_pipelines()` is deprecated and will be "
        "removed in a future release. Please use "
        "`zenml.client.Client().list_pipelines()` instead."
    )
    return Client().list_pipelines().items


@track(event=AnalyticsEvent.GET_PIPELINE)
def get_pipeline(
    pipeline: Union["Pipeline", Type["Pipeline"], str],
    version: Optional[str] = None,
) -> Optional[Union["PipelineView", "PipelineResponseModel"]]:
    """Fetches a post-execution pipeline view.

    Use it in one of these ways:
    ```python
    from zenml.post_execution import get_pipeline

    # Get the pipeline by name
    get_pipeline("first_pipeline")

    # Get the pipeline by supplying the original pipeline class
    get_pipeline(first_pipeline)

    # Get the pipeline by supplying an instance of the original pipeline class
    get_pipeline(first_pipeline())
    ```

    If the specified pipeline does not (yet) exist within the repository,
    `None` will be returned.

    Args:
        pipeline: Name, class or instance of the pipeline.
        version: Optional pipeline version. Behavior depends on `pipeline`:
            - If `pipeline` is a pipeline instance, this argument is ignored.
            - If `pipeline` is a pipeline class or name, then this argument
            specifies the version of the pipeline to return. If not given, a
            `PipelineView` will be returned that contains all versions and
            all runs of this pipeline name/class.

    Returns:
        A post-execution view for the given pipeline name, class, or instance
        or `None` if it doesn't exist.

    Raises:
        RuntimeError: If the pipeline was not specified correctly.
    """
    from zenml.new.pipelines.pipeline import Pipeline

    # Pipeline instance: find the corresponding pipeline version in the DB.
    if isinstance(pipeline, Pipeline):
        pipeline_model = pipeline._get_registered_model()
        if pipeline_model:
            return pipeline_model
        else:
            return None

    # Otherwise, for pipeline name or class, determine the name first.
    if isinstance(pipeline, str):
        pipeline_name = pipeline

    elif isinstance(pipeline, type) and issubclass(pipeline, Pipeline):
        pipeline_name = pipeline.__name__
    else:
        raise RuntimeError(
            f"Pipeline must be specified as a name (string), a class or an "
            f"instance of a class. Got type `{type(pipeline)}` instead."
        )

    # If no version is given, return a `PipelineView` that contains all
    # versions and all runs of this pipeline name/class.
    if version is None:
        class_view = PipelineView(name=pipeline_name)
        if class_view.runs:
            return class_view
        return None

    # Otherwise, find the corresponding pipeline version in the DB.
    client = Client()
    try:
        return client.get_pipeline(
            name_id_or_prefix=pipeline_name, version=version
        )
    except KeyError:
        return None


class PipelineView:
    """Post-execution class for a pipeline name/class."""

    def __init__(self, name: str):
        """Initializes a post-execution class for a pipeline name/class.

        Args:
            name: The name of the pipeline.
        """
        self.name = name

    @property
    def versions(self) -> List["PipelineResponseModel"]:
        """Returns all versions/instances of this pipeline name/class.

        Returns:
            A list of all versions of this pipeline.
        """
        client = Client()

        pipelines = depaginate(
            partial(
                client.list_pipelines,
                workspace_id=client.active_workspace.id,
                name=self.name,
                sort_by="desc:created",
            )
        )
        return pipelines

    @property
    def num_runs(self) -> int:
        """Returns the number of runs of this pipeline name/class.

        This is the sum of all runs of all versions of this pipeline.

        Returns:
            The number of runs of this pipeline name/class.
        """
        return sum(version.num_runs for version in self.versions)

    @property
    def runs(self) -> List["PipelineRunResponseModel"]:
        """Returns the last 50 stored runs of this pipeline name/class.

        The runs are returned in reverse chronological order, so the latest
        run will be the first element in this list.

        Returns:
            A list of all stored runs of this pipeline name/class.
        """
        all_runs = [
            run for version in self.versions for run in (version.runs or [])
        ]
        sorted_runs = sorted(all_runs, key=lambda x: x.created, reverse=True)
        return sorted_runs[:50]

    def __eq__(self, other: Any) -> bool:
        """Compares this pipeline class view to another object.

        Args:
            other: The other object to compare to.

        Returns:
            Whether the other object is a pipeline class view with same name.
        """
        if not isinstance(other, PipelineView):
            return False
        return self.name == other.name
