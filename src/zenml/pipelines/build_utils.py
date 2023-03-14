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
"""Pipeline build utilities."""
import hashlib
import platform
from types import FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Union,
)
from uuid import UUID

import zenml
from zenml.client import Client
from zenml.code_repositories import BaseCodeRepository
from zenml.config.docker_settings import SourceFileMode
from zenml.config.step_configurations import StepConfigurationUpdate
from zenml.logger import get_logger
from zenml.models import (
    PipelineBuildRequestModel,
    PipelineBuildResponseModel,
)
from zenml.models.pipeline_build_models import (
    BuildItem,
    PipelineBuildBaseModel,
)
from zenml.models.pipeline_deployment_models import PipelineDeploymentBaseModel
from zenml.stack import Stack
from zenml.utils import (
    source_utils_v2,
)
from zenml.utils.pipeline_docker_image_builder import (
    PipelineDockerImageBuilder,
)

if TYPE_CHECKING:
    from zenml.code_repositories import LocalRepository
    from zenml.config.build_configuration import BuildConfiguration
    from zenml.config.source import Source

    StepConfigurationUpdateOrDict = Union[
        Dict[str, Any], StepConfigurationUpdate
    ]
    HookSpecification = Union[str, "Source", FunctionType]

logger = get_logger(__name__)


def verify_local_repository(
    deployment: "PipelineDeploymentBaseModel",
    local_repo: Optional["LocalRepository"],
) -> Optional[BaseCodeRepository]:
    if deployment.requires_code_download:
        if not local_repo:
            raise RuntimeError(
                "The `DockerSettings` of the pipeline or one of its "
                "steps specify that code should be included in the "
                "Docker image (`source_files='download'`), but there is no "
                "code repository active at your current source root "
                f"`{source_utils_v2.get_source_root()}`."
            )
        elif local_repo.is_dirty:
            raise RuntimeError(
                "The `DockerSettings` of the pipeline or one of its "
                "steps specify that code should be included in the "
                "Docker image (`source_files='download'`), but the code "
                "repository active at your current source root "
                f"`{source_utils_v2.get_source_root()}` has uncommited "
                "changes."
            )
        elif local_repo.has_local_changes:
            raise RuntimeError(
                "The `DockerSettings` of the pipeline or one of its "
                "steps specify that code should be included in the "
                "Docker image (`source_files='download'`), but the code "
                "repository active at your current source root "
                f"`{source_utils_v2.get_source_root()}` has unpushed "
                "changes."
            )

    code_repository = None

    if local_repo and not local_repo.has_local_changes:
        model = Client().get_code_repository(local_repo.code_repository_id)
        code_repository = BaseCodeRepository.from_model(model)

    return code_repository


def reuse_or_create_pipeline_build(
    deployment: "PipelineDeploymentBaseModel",
    pipeline_version_hash: str,
    allow_build_reuse: bool,
    pipeline_id: Optional[UUID] = None,
    build: Union["UUID", "PipelineBuildBaseModel", None] = None,
    code_repository: Optional["BaseCodeRepository"] = None,
) -> Optional["PipelineBuildResponseModel"]:
    """Loads or creates a pipeline build.

    Args:
        deployment: The pipeline deployment for which to load or create the
            build.
        pipeline_spec: Spec of the pipeline.
        allow_code_download: If True, the build is allowed to download code
            from the code repository.
        allow_build_reuse: If True, the build is allowed to reuse an
            existing build.
        pipeline_id: Optional ID of the pipeline to reference in the build.
        build: Optional existing build. If given, the build will be loaded
            (or registered) in the database. If not given, a new build will
            be created.
        code_repository: Optional code repository to use for the build.

    Returns:
        The build response.
    """
    if not build:
        if (
            allow_build_reuse
            and code_repository
            and not deployment.requires_included_files
        ):
            existing_build = find_existing_build(
                deployment=deployment, code_repository=code_repository
            )

            if existing_build:
                logger.info(
                    "Reusing existing build `%s` for stack `%s`.",
                    existing_build.id,
                    Client().active_stack.name,
                )
                return existing_build

        return create_pipeline_build(
            deployment=deployment,
            pipeline_id=pipeline_id,
            code_repository=code_repository,
        )

    build_model = None

    if isinstance(build, UUID):
        build_model = Client().zen_store.get_build(build_id=build)
    else:
        build_request = PipelineBuildRequestModel(
            user=Client().active_user.id,
            workspace=Client().active_workspace.id,
            stack=Client().active_stack_model.id,
            pipeline=pipeline_id,
            **build.dict(),
        )
        build_model = Client().zen_store.create_build(build=build_request)

    verify_custom_build(
        build=build_model,
        deployment=deployment,
        pipeline_version_hash=pipeline_version_hash,
        code_repository=code_repository,
    )

    return build_model


def find_existing_build(
    deployment: "PipelineDeploymentBaseModel",
    code_repository: Optional["BaseCodeRepository"] = None,
) -> Optional["PipelineBuildResponseModel"]:
    client = Client()
    stack = client.active_stack

    python_version_prefix = ".".join(platform.python_version_tuple()[:2])
    required_builds = stack.get_docker_builds(deployment=deployment)
    build_checksum = compute_build_checksum(
        required_builds, stack=stack, code_repository=code_repository
    )

    matches = client.list_builds(
        sort_by="desc:created",
        size=1,
        stack_id=stack.id,
        # The build is local and it's not clear whether the images
        # exist on the current machine or if they've been overwritten.
        # TODO: Should we support this by storing the unique Docker ID for
        # the image and checking if an image with that ID exists locally?
        is_local=False,
        # The build contains some code which might be different than the
        # local code the user is expecting to run
        contains_code=False,
        zenml_version=zenml.__version__,
        # Match all patch versions of the same Python major + minor
        python_version=f"startswith:{python_version_prefix}",
        checksum=build_checksum,
    )

    if not matches.items:
        return None

    return matches[0]


def create_pipeline_build(
    deployment: "PipelineDeploymentBaseModel",
    pipeline_id: Optional[UUID] = None,
    code_repository: Optional["BaseCodeRepository"] = None,
) -> Optional["PipelineBuildResponseModel"]:
    """Builds images and registers the output in the server.

    Args:
        deployment: The compiled pipeline deployment.
        allow_code_download: If True, the build is allowed to download code
            from the code repository.
        pipeline_id: The ID of the pipeline.

    Returns:
        The build output.

    Raises:
        RuntimeError: If multiple builds with the same key but different
            settings were specified.
    """
    client = Client()
    stack = client.active_stack
    required_builds = stack.get_docker_builds(deployment=deployment)

    if not required_builds:
        logger.debug("No docker builds required.")
        return None

    logger.info(
        "Building Docker image(s) for pipeline `%s`.",
        deployment.pipeline_configuration.name,
    )

    docker_image_builder = PipelineDockerImageBuilder()
    images: Dict[str, BuildItem] = {}
    checksums: Dict[str, str] = {}
    allow_code_download = code_repository is not None

    for build_config in required_builds:
        combined_key = PipelineBuildBaseModel.get_image_key(
            component_key=build_config.key, step=build_config.step_name
        )
        checksum = build_config.compute_settings_checksum(
            stack=stack, code_repository=code_repository
        )

        if combined_key in images:
            previous_checksum = images[combined_key].settings_checksum

            if previous_checksum != checksum:
                raise RuntimeError(
                    f"Trying to build image for key `{combined_key}` but "
                    "an image for this key was already built with a "
                    "different configuration. This happens if multiple "
                    "stack components specified Docker builds for the same "
                    "key in the `StackComponent.get_docker_builds(...)` "
                    "method. If you're using custom components, make sure "
                    "to provide unique keys when returning your build "
                    "configurations to avoid this error."
                )
            else:
                continue

        if checksum in checksums:
            item_key = checksums[checksum]
            image_name_or_digest = images[item_key].image
            contains_code = images[item_key].contains_code
        else:
            tag = deployment.pipeline_configuration.name
            if build_config.step_name:
                tag += f"-{build_config.step_name}"
            tag += f"-{build_config.key}"

            include_files = (
                build_config.settings.source_files == SourceFileMode.INCLUDE
                or (
                    build_config.settings.source_files
                    == SourceFileMode.DOWNLOAD_OR_INCLUDE
                    and not allow_code_download
                )
            )
            download_files = (
                build_config.settings.source_files == SourceFileMode.DOWNLOAD
                or (
                    build_config.settings.source_files
                    == SourceFileMode.DOWNLOAD_OR_INCLUDE
                    and allow_code_download
                )
            )
            image_name_or_digest = docker_image_builder.build_docker_image(
                docker_settings=build_config.settings,
                tag=tag,
                stack=stack,
                include_files=include_files,
                download_files=download_files,
                entrypoint=build_config.entrypoint,
                extra_files=build_config.extra_files,
                code_repository=code_repository,
            )
            contains_code = include_files

        images[combined_key] = BuildItem(
            image=image_name_or_digest,
            settings_checksum=checksum,
            contains_code=contains_code,
        )
        checksums[checksum] = combined_key

    logger.info("Finished building Docker image(s).")

    is_local = stack.container_registry is None
    contains_code = any(item.contains_code for item in images.values())
    build_checksum = compute_build_checksum(
        required_builds, stack=stack, code_repository=code_repository
    )

    build_request = PipelineBuildRequestModel(
        user=client.active_user.id,
        workspace=client.active_workspace.id,
        stack=client.active_stack_model.id,
        pipeline=pipeline_id,
        is_local=is_local,
        contains_code=contains_code,
        images=images,
        zenml_version=zenml.__version__,
        python_version=platform.python_version(),
        checksum=build_checksum,
    )
    return client.zen_store.create_build(build_request)


def compute_build_checksum(
    items: List["BuildConfiguration"],
    stack: "Stack",
    code_repository: Optional["BaseCodeRepository"] = None,
) -> str:
    hash_ = hashlib.md5()

    for item in items:
        key = PipelineBuildBaseModel.get_image_key(
            component_key=item.key, step=item.step_name
        )
        settings_checksum = item.compute_settings_checksum(
            stack=stack, code_repository=code_repository
        )

        hash_.update(key.encode())
        hash_.update(settings_checksum.encode())

    return hash_.hexdigest()


def verify_custom_build(
    build: "PipelineBuildResponseModel",
    deployment: "PipelineDeploymentBaseModel",
    pipeline_version_hash: str,
    code_repository: Optional["BaseCodeRepository"] = None,
) -> None:
    """Validates the build of a pipeline deployment.

    Args:
        deployment: The deployment for which to validate the build.
    """
    stack = Client().active_stack
    required_builds = stack.get_docker_builds(deployment=deployment)

    if build.stack and build.stack.id != stack.id:
        logger.warning(
            "The stack `%s` used for the build `%s` is not the same as the "
            "stack `%s` that the pipeline will run on. This could lead "
            "to issues if the stacks have different build requirements.",
            build.stack.name,
            build.id,
            stack.name,
        )

    if build.pipeline:
        if build.pipeline.version_hash != pipeline_version_hash:
            logger.warning(
                "The pipeline associated with the build you "
                "specified for this run has a different spec "
                "or step code. This might lead to unexpected "
                "behavior as this pipeline run will use the "
                "code that was included in the Docker images which "
                "might differ from the code in your client "
                "environment."
            )

    if build.contains_code:
        logger.warning(
            "The build you specified for this run contains code and will run "
            "with the step code that was included in the Docker images which "
            "might differ from the local code in your client environment."
        )

    if build.requires_code_download and not code_repository:
        raise RuntimeError(
            "The build you specified does not include code but code download "
            "not possible. This might be because you don't have a code "
            "repository registered or the code repository contains local "
            "changes."
        )

    if build.checksum:
        build_checksum = compute_build_checksum(
            required_builds, stack=stack, code_repository=code_repository
        )
        if build_checksum != build.checksum:
            logger.warning(
                "The Docker settings used for the build `%s` are "
                "not the same as currently specified for you pipeline. "
                "This means that the build you specified to run this "
                "pipeline might be outdated and most likely contains "
                "outdated requirements.",
                build.id,
            )

    else:
        # No checksum given for the entire build, we manually check that
        # all the images exist and the setting match
        for build_config in required_builds:
            try:
                image = build.get_image(
                    component_key=build_config.key,
                    step=build_config.step_name,
                )
            except KeyError:
                raise RuntimeError(
                    "The build you specified is missing an image for key: "
                    f"{build_config.key}."
                )

            if build_config.compute_settings_checksum(
                stack=stack, code_repository=code_repository
            ) != build.get_settings_checksum(
                component_key=build_config.key, step=build_config.step_name
            ):
                logger.warning(
                    "The Docker settings used to build the image `%s` are "
                    "not the same as currently specified for you pipeline. "
                    "This means that the build you specified to run this "
                    "pipeline might be outdated and most likely contains "
                    "outdated code or requirements.",
                    image,
                )

    if build.is_local:
        logger.warning(
            "You manually specified a local build to run your pipeline. "
            "This might lead to errors if the images don't exist on "
            "your local machine or the image tags have been "
            "overwritten since the original build happened."
        )
