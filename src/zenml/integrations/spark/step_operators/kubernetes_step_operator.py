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
import subprocess
from typing import AbstractSet, ClassVar, Dict, List, Optional

from zenml.constants import ENV_ZENML_CONFIG_PATH
from zenml.integrations.spark import SPARK_KUBERNETES_STEP_OPERATOR
from zenml.io.fileio import copy
from zenml.logger import get_logger
from zenml.repository import Repository
from zenml.step_operators import BaseStepOperator, entrypoint
from zenml.utils.docker_utils import build_docker_image, get_image_digest
from zenml.utils.io_utils import write_file_contents_as_string
from zenml.utils.source_utils import get_source_root_path

logger = get_logger(__name__)

LOCAL_ENTRYPOINT = entrypoint.__file__
ZENML_DIR = "/zenml/"
APP_DIR = "/app/"
CONTAINER_ZENML_CONFIG_DIR = ".zenconfig"


def generate_dockerfile_contents(
    base_image: str,
    requirements: Optional[AbstractSet[str]] = None,
    environment_vars: Optional[Dict[str, str]] = None,
) -> str:
    """Generates a Dockerfile.

    Args:
        base_image: The image to use as base for the dockerfile.
        requirements: Optional list of pip requirements to install.
        environment_vars: Optional dict of environment variables to set.

    Returns:
        Contents of a dockerfile.
    """
    # Create the base
    lines = [
        f"FROM {base_image}",
        "USER root",  # required to install the requirements
        f"WORKDIR {ZENML_DIR}",
        f"COPY entrypoint.py .",
        "RUN apt-get -y update",
        "RUN apt-get -y install git",
    ]

    # Add env variables
    if environment_vars:
        for key, value in environment_vars.items():
            lines.append(f"ENV {key.upper()}={value}")

    # Install requirements
    if requirements:
        lines.append(
            f"RUN pip install --user --no-cache {' '.join(sorted(requirements))}"
        )

    # Copy the repo and config
    lines.extend(
        [
            f"WORKDIR {APP_DIR}",
            "COPY . .",
            "RUN chmod -R a+rw .",
            f"ENV {ENV_ZENML_CONFIG_PATH}={APP_DIR}{CONTAINER_ZENML_CONFIG_DIR}",
        ]
    )

    return "\n".join(lines)


class KubernetesSparkStepOperator(BaseStepOperator):
    # Instance parameters
    master: str
    deploy_mode: str = "cluster"
    configuration_properties: List[str] = []

    # Class configuration
    FLAVOR: ClassVar[str] = SPARK_KUBERNETES_STEP_OPERATOR

    @staticmethod
    def _build_docker_image(
        pipeline_name,
        requirements,
    ):
        repo = Repository()
        container_registry = repo.active_stack.container_registry
        if not container_registry:
            raise RuntimeError("Missing container registry")
        registry_uri = container_registry.uri.rstrip("/")
        image_name = f"{registry_uri}/spark-zenml:{pipeline_name}"

        """Create the proper image to use for spark on k8s."""
        base_image = f"{registry_uri}/spark-base:1.0"

        dockerfile_content = generate_dockerfile_contents(
            base_image=base_image, requirements=requirements
        )
        dockerfile_path = os.path.join(os.getcwd(), "DOCKERFILE")
        entrypoint_path = os.path.join(os.getcwd(), "entrypoint.py")
        copy(LOCAL_ENTRYPOINT, entrypoint_path, overwrite=True)
        write_file_contents_as_string(
            dockerfile_path,
            dockerfile_content,
        )

        build_docker_image(
            image_name=image_name,
            build_context_path=get_source_root_path(),
            dockerfile_path=dockerfile_path,
            base_image=base_image,
            requirements=requirements,
        )

        container_registry.push_image(image_name)
        return get_image_digest(image_name) or image_name

    def _create_base_command(self):
        """Create the base command for spark-submit."""
        command = [
            "spark-submit",
            "--master",
            f"k8s://{self.master}",
            "--deploy-mode",
            self.deploy_mode,
        ]
        return command

    def _create_configurations(self, image_name: str):
        """Build the configuration parameters for the spark-submit command."""
        configurations = [
            "--conf",
            f"spark.kubernetes.container.image={image_name}",
            "--conf",
            "spark.kubernetes.namespace=spark-namespace",
            "--conf",
            "spark.kubernetes.authenticate.driver.serviceAccountName=spark-service-account",
        ]

        for o in self.configuration_properties:
            configurations.extend(["--conf", o])
        return configurations

    @staticmethod
    def _create_spark_app_command(entrypoint_command):
        """Build the python entrypoint command for the spark-submit."""
        command = [
            f"local://{ZENML_DIR}{os.path.basename(entrypoint.__file__)}"
        ]

        for arg in [
            "--main_module",
            "--step_source_path",
            "--execution_info_path",
            "--input_artifact_types_path",
        ]:
            i = entrypoint_command.index(arg)
            command.extend([arg, entrypoint_command[i + 1]])

        return command

    def launch(
        self,
        pipeline_name: str,
        run_name: str,
        requirements: List[str],
        entrypoint_command: List[str],
    ) -> None:
        """Launch the spark job with spark-submit."""
        # Build the docker image to use for spark on Kubernetes
        image_name = self._build_docker_image(pipeline_name, requirements)

        # Base command
        base_command = self._create_base_command()

        # Add configurations
        configurations = self._create_configurations(image_name=image_name)
        base_command.extend(configurations)

        # Add the spark app
        spark_app_command = self._create_spark_app_command(entrypoint_command)
        base_command.extend(spark_app_command)

        command = " ".join(base_command)

        # Execute the command
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=True,
        )

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            raise RuntimeError(stderr)
        print(stdout)
