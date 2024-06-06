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
"""ZenML logging handler."""

import os
import re
import sys
import time
from contextvars import ContextVar
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Any, Callable, List, Optional, Type, Union
from uuid import UUID, uuid4

from zenml.artifact_stores import BaseArtifactStore
from zenml.artifacts.utils import (
    _load_artifact_store,
    _load_file_from_artifact_store,
)
from zenml.client import Client
from zenml.io import fileio
from zenml.logger import get_logger
from zenml.logging import (
    STEP_LOGS_STORAGE_INTERVAL_SECONDS,
    STEP_LOGS_STORAGE_MAX_MESSAGES,
)
from zenml.zen_stores.base_zen_store import BaseZenStore

# Get the logger
logger = get_logger(__name__)

redirected: ContextVar[bool] = ContextVar("redirected", default=False)

LOGS_EXTENSION = ".log"


def remove_ansi_escape_codes(text: str) -> str:
    """Auxiliary function to remove ANSI escape codes from a given string.

    Args:
        text: the input string

    Returns:
        the version of the input string where the escape codes are removed.
    """
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def prepare_logs_folder_uri(
    artifact_store: "BaseArtifactStore",
    step_name: str,
    log_key: Optional[str] = None,
) -> str:
    """Generates and prepares a URI for the log folder for a step.

    Args:
        artifact_store: The artifact store on which the artifact will be stored.
        step_name: Name of the step.
        log_key: The unique identification key of the log file.

    Returns:
        The URI of the log folder.
    """
    if log_key is None:
        log_key = str(uuid4())

    logs_base_uri = os.path.join(
        artifact_store.path,
        step_name,
        "logs",
    )

    # Create the dir
    if not artifact_store.exists(logs_base_uri):
        artifact_store.makedirs(logs_base_uri)

    # Delete the file if it already exists
    logs_uri_folder = os.path.join(logs_base_uri, log_key)
    if artifact_store.exists(logs_uri_folder):
        logger.warning(
            f"Logs directory {logs_uri_folder} already exists! Removing old log directory..."
        )
        artifact_store.remove(logs_uri_folder)

    artifact_store.makedirs(logs_uri_folder)
    return logs_uri_folder


def fetch_logs(
    zen_store: "BaseZenStore",
    artifact_store_id: Union[str, UUID],
    logs_uri: str,
) -> str:
    artifact_store = _load_artifact_store(artifact_store_id, zen_store)
    if logs_uri.endswith(LOGS_EXTENSION):
        return str(
            _load_file_from_artifact_store(
                logs_uri, artifact_store=artifact_store, mode="r"
            )
        )
    else:
        files = artifact_store.listdir(logs_uri)
        files.sort()
        ret = []
        for file in files:
            ret.append(
                str(
                    _load_file_from_artifact_store(
                        os.path.join(logs_uri, str(file)),
                        artifact_store=artifact_store,
                        mode="r",
                    )
                )
            )
        return "".join(ret)


class StepLogsStorage:
    """Helper class which buffers and stores logs to a given URI."""

    def __init__(
        self,
        logs_uri_folder: str,
        max_messages: int = STEP_LOGS_STORAGE_MAX_MESSAGES,
        time_interval: int = STEP_LOGS_STORAGE_INTERVAL_SECONDS,
    ) -> None:
        """Initialization.

        Args:
            logs_uri_folder: the URI of the log folder.
            max_messages: the maximum number of messages to save in the buffer.
            time_interval: the amount of seconds before the buffer gets saved
                automatically.
        """
        # Parameters
        self.logs_uri_folder = logs_uri_folder
        self.max_messages = max_messages
        self.time_interval = time_interval

        # State
        self.buffer: List[str] = []
        self.disabled_buffer: List[str] = []
        self.last_save_time = time.time()
        self.disabled = False

    def write(self, text: str) -> None:
        """Main write method.

        Args:
            text: the incoming string.
        """
        if text == "\n":
            return

        if not self.disabled:
            self.buffer.append(text)
            self.save_to_file()

    @property
    def _is_write_needed(self) -> bool:
        """Checks whether the buffer needs to be written to disk.

        Returns:
            whether the buffer needs to be written to disk.
        """
        return (
            len(self.buffer) >= self.max_messages
            or time.time() - self.last_save_time >= self.time_interval
        )

    def save_to_file(self, force: bool = False) -> None:
        """Method to save the buffer to the given URI.

        Args:
            force: whether to force a save even if the write conditions not met.
        """
        if not self.disabled and (self._is_write_needed or force):
            # IMPORTANT: keep this as the first code line in this method! The
            # code that follows might still emit logging messages, which will
            # end up triggering this method again, causing an infinite loop.
            self.disabled = True

            artifact_store = Client().active_stack.artifact_store
            try:
                if self.buffer:
                    with artifact_store.open(
                        os.path.join(
                            self.logs_uri_folder,
                            f"{time.time()}{LOGS_EXTENSION}",
                        ),
                        "w",
                    ) as file:
                        for message in self.buffer:
                            file.write(
                                remove_ansi_escape_codes(message) + "\n"
                            )

            except (OSError, IOError) as e:
                # This exception can be raised if there are issues with the
                # underlying system calls, such as reaching the maximum number
                # of open files, permission issues, file corruption, or other
                # I/O errors.
                logger.error(f"Error while trying to write logs: {e}")
            finally:
                self.buffer = []
                self.last_save_time = time.time()

                self.disabled = False

    def merge_log_files(self) -> None:
        """Merges all log files into one in the given URI.

        Called on the logging context exit.
        """

        artifact_store = Client().active_stack.artifact_store
        files = artifact_store.listdir(self.logs_uri_folder)
        if len(files) > 1:
            files.sort()
            logger.debug("Log files count: %s", len(files))

            with TemporaryDirectory() as temp_dir:
                try:
                    local_log_file = os.path.join(
                        temp_dir, f"merged{LOGS_EXTENSION}"
                    )
                    # dump all logs to a local file first
                    with open(local_log_file, "w") as merged_file:
                        for file in files:
                            merged_file.write(
                                str(
                                    _load_file_from_artifact_store(
                                        os.path.join(
                                            self.logs_uri_folder, str(file)
                                        ),
                                        artifact_store=artifact_store,
                                        mode="r",
                                    )
                                )
                            )

                    # copy it over to the artifact store
                    fileio.copy(
                        local_log_file,
                        os.path.join(
                            self.logs_uri_folder, f"full_log{LOGS_EXTENSION}"
                        ),
                    )
                except Exception as e:
                    logger.warning(f"Failed to merge log files. {e}")
                else:
                    # clean up left over files
                    for file in files:
                        artifact_store.remove(
                            os.path.join(self.logs_uri_folder, str(file))
                        )


class StepLogsStorageContext:
    """Context manager which patches stdout and stderr during step execution."""

    def __init__(self, logs_uri: str) -> None:
        """Initializes and prepares a storage object.

        Args:
            logs_uri: the URI of the logs file.
        """
        self.storage = StepLogsStorage(logs_uri_folder=logs_uri)

    def __enter__(self) -> "StepLogsStorageContext":
        """Enter condition of the context manager.

        Wraps the `write` method of both stderr and stdout, so each incoming
        message gets stored in the step logs storage.

        Returns:
            self
        """
        self.stdout_write = getattr(sys.stdout, "write")
        self.stdout_flush = getattr(sys.stdout, "flush")

        self.stderr_write = getattr(sys.stderr, "write")
        self.stderr_flush = getattr(sys.stderr, "flush")

        setattr(sys.stdout, "write", self._wrap_write(self.stdout_write))
        setattr(sys.stdout, "flush", self._wrap_flush(self.stdout_flush))

        setattr(sys.stderr, "write", self._wrap_write(self.stdout_write))
        setattr(sys.stderr, "flush", self._wrap_flush(self.stdout_flush))

        redirected.set(True)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit condition of the context manager.

        Args:
            exc_type: The class of the exception
            exc_val: The instance of the exception
            exc_tb: The traceback of the exception

        Restores the `write` method of both stderr and stdout.
        """
        self.storage.save_to_file(force=True)
        self.storage.merge_log_files()

        setattr(sys.stdout, "write", self.stdout_write)
        setattr(sys.stdout, "flush", self.stdout_flush)

        setattr(sys.stderr, "write", self.stderr_write)
        setattr(sys.stderr, "flush", self.stderr_flush)

        redirected.set(False)

    def _wrap_write(self, method: Callable[..., Any]) -> Callable[..., Any]:
        """Wrapper function that utilizes the storage object to store logs.

        Args:
            method: the original write method

        Returns:
            the wrapped write method.
        """

        def wrapped_write(*args: Any, **kwargs: Any) -> Any:
            output = method(*args, **kwargs)
            if args:
                self.storage.write(args[0])
            return output

        return wrapped_write

    def _wrap_flush(self, method: Callable[..., Any]) -> Callable[..., Any]:
        """Wrapper function that flushes the buffer of the storage object.

        Args:
            method: the original flush method

        Returns:
            the wrapped flush method.
        """

        def wrapped_flush(*args: Any, **kwargs: Any) -> Any:
            output = method(*args, **kwargs)
            self.storage.save_to_file()
            return output

        return wrapped_flush
