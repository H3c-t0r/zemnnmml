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
import platform
import shutil
import time
from multiprocessing import Process

import pytest
import requests
import uvicorn

from zenml.config.profile_config import ProfileConfiguration
from zenml.constants import (
    DEFAULT_SERVICE_START_STOP_TIMEOUT,
    ENV_ZENML_PROFILE_CONFIGURATION,
    REPOSITORY_DIRECTORY_NAME,
    ZEN_SERVICE_ENTRYPOINT,
    ZEN_SERVICE_IP,
)
from zenml.enums import StackComponentType, StoreType
from zenml.exceptions import StackComponentExistsError, StackExistsError
from zenml.logger import get_logger
from zenml.orchestrators import LocalOrchestrator
from zenml.stack import Stack
from zenml.stack_stores import (
    BaseStackStore,
    LocalStackStore,
    RestStackStore,
    SqlStackStore,
)
from zenml.stack_stores.models import StackComponentWrapper, StackWrapper
from zenml.utils.networking_utils import scan_for_available_port

logger = get_logger(__name__)


not_windows = platform.system() != "Windows"
store_types = [StoreType.LOCAL, StoreType.SQL] + [StoreType.REST] * not_windows


@pytest.fixture(params=store_types)
def fresh_stack_store(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> BaseStackStore:
    store_type = request.param
    tmp_path = tmp_path_factory.mktemp(f"{store_type.value}_stack_store")
    os.mkdir(tmp_path / REPOSITORY_DIRECTORY_NAME)

    if store_type == StoreType.LOCAL:
        yield LocalStackStore().initialize(str(tmp_path))
    elif store_type == StoreType.SQL:
        yield SqlStackStore().initialize(f"sqlite:///{tmp_path / 'store.db'}")
    elif store_type == StoreType.REST:
        # create temporary stack store and profile configuration for unit tests
        backing_stack_store = LocalStackStore().initialize(str(tmp_path))
        store_profile = ProfileConfiguration(
            name=f"test_profile_{hash(str(tmp_path))}",
            store_url=backing_stack_store.url,
            store_type=backing_stack_store.type,
        )
        # use environment file to pass profile into the zen service process
        env_file = str(tmp_path / "environ.env")
        with open(env_file, "w") as f:
            f.write(
                f"{ENV_ZENML_PROFILE_CONFIGURATION}='{store_profile.json()}'"
            )
        port = scan_for_available_port(start=8003, stop=9000)
        if not port:
            raise RuntimeError("No available port found.")
        proc = Process(
            target=uvicorn.run,
            args=(ZEN_SERVICE_ENTRYPOINT,),
            kwargs=dict(
                host=ZEN_SERVICE_IP,
                port=port,
                log_level="info",
                env_file=env_file,
            ),
            daemon=True,
        )
        url = f"http://{ZEN_SERVICE_IP}:{port}"
        proc.start()

        # wait 10 seconds for server to start
        for t in range(DEFAULT_SERVICE_START_STOP_TIMEOUT):
            try:
                if requests.head(f"{url}/health").status_code == 200:
                    break
                else:
                    time.sleep(1)
            except Exception:
                time.sleep(1)
        else:
            proc.kill()
            raise RuntimeError("Failed to start ZenService server.")

        yield RestStackStore().initialize(url)

        # make sure there's still a server and tear down
        assert proc.is_alive()
        proc.kill()
        # wait 10 seconds for process to be killed:
        for t in range(DEFAULT_SERVICE_START_STOP_TIMEOUT):
            if proc.is_alive():
                time.sleep(1)
            else:
                break
        else:
            raise RuntimeError("Failed to shutdown ZenService server.")
    else:
        raise NotImplementedError(f"No StackStore for {store_type}")

    shutil.rmtree(tmp_path)


def test_register_deregister_stacks(fresh_stack_store: BaseStackStore):
    """Test creating a new stack store."""

    stack = Stack.default_local_stack()

    # stack store is pre-initialized with the default stack
    stack_store = fresh_stack_store
    assert len(stack_store.stacks) == 1
    assert len(stack_store.stack_configurations) == 1

    # retrieve the default stack
    got_stack = stack_store.get_stack(stack.name)
    assert got_stack.name == stack.name
    stack_configuration = stack_store.get_stack_configuration(stack.name)
    assert set(stack_configuration) == {
        "orchestrator",
        "metadata_store",
        "artifact_store",
    }
    assert stack_configuration[StackComponentType.ORCHESTRATOR] == "default"

    # can't register the same stack twice or another stack with the same name
    with pytest.raises(StackExistsError):
        stack_store.register_stack(StackWrapper.from_stack(stack))
    with pytest.raises(StackExistsError):
        stack_store.register_stack(StackWrapper(name=stack.name, components=[]))

    # can't remove a stack that doesn't exist:
    with pytest.raises(KeyError):
        stack_store.deregister_stack("overflow")

    # remove the default stack
    stack_store.deregister_stack(stack.name)
    assert len(stack_store.stacks) == 0
    with pytest.raises(KeyError):
        _ = stack_store.get_stack(stack.name)

    # now can add another stack with the same name
    stack_store.register_stack(StackWrapper(name=stack.name, components=[]))
    assert len(stack_store.stacks) == 1


def test_register_deregister_components(fresh_stack_store: BaseStackStore):
    """Test adding and removing stack components."""

    required_components = {
        StackComponentType.ARTIFACT_STORE,
        StackComponentType.METADATA_STORE,
        StackComponentType.ORCHESTRATOR,
    }

    # stack store starts off with the default stack
    stack_store = fresh_stack_store
    for component_type in StackComponentType:
        component_type = StackComponentType(component_type)
        if component_type in required_components:
            assert len(stack_store.get_stack_components(component_type)) == 1
        else:
            assert len(stack_store.get_stack_components(component_type)) == 0

    # get a component
    orchestrator = stack_store.get_stack_component(
        StackComponentType.ORCHESTRATOR, "default"
    )

    assert orchestrator.flavor == "local"
    assert orchestrator.name == "default"

    # can't add another orchestrator of same name
    with pytest.raises(StackComponentExistsError):
        stack_store.register_stack_component(
            StackComponentWrapper.from_component(
                LocalOrchestrator(
                    name="default",
                )
            )
        )

    # but can add one if it has a different name
    stack_store.register_stack_component(
        StackComponentWrapper.from_component(
            LocalOrchestrator(
                name="local_orchestrator_part_2_the_remix",
            )
        )
    )
    assert (
        len(stack_store.get_stack_components(StackComponentType.ORCHESTRATOR))
        == 2
    )

    # can't delete an orchestrator that's part of a stack
    with pytest.raises(ValueError):
        stack_store.deregister_stack_component(
            StackComponentType.ORCHESTRATOR, "default"
        )

    # but can if the stack is deleted first
    stack_store.deregister_stack("default")
    stack_store.deregister_stack_component(
        StackComponentType.ORCHESTRATOR, "default"
    )
    assert (
        len(stack_store.get_stack_components(StackComponentType.ORCHESTRATOR))
        == 1
    )
