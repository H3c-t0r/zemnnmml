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
from pathlib import Path
from typing import Optional

import click
from rich.style import Style

from zenml.cli.cli import cli
from zenml.cli.text_utils import (
    zenml_go_email_prompt,
    zenml_go_notebook_tutorial_message,
    zenml_go_privacy_message,
    zenml_go_thank_you_message,
    zenml_go_welcome_message,
)
from zenml.cli.utils import confirmation, declare, error, warning
from zenml.config.global_config import GlobalConfiguration
from zenml.console import console
from zenml.constants import REPOSITORY_DIRECTORY_NAME
from zenml.exceptions import GitNotFoundError, InitializationException
from zenml.io import fileio
from zenml.io.utils import get_global_config_directory
from zenml.logger import get_logger
from zenml.repository import Repository
from zenml.utils.analytics_utils import identify_user

logger = get_logger(__name__)
# WT_SESSION is a Windows Terminal specific environment variable. If it
# exists, we are on the latest Windows Terminal that supports emojis
_SHOW_EMOJIS = not os.name == "nt" or os.environ.get("WT_SESSION")

TUTORIAL_REPO = "https://github.com/zenml-io/zenbytes"


@cli.command("init", help="Initialize a ZenML repository.")
@click.option(
    "--path",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, path_type=Path
    ),
)
def init(path: Optional[Path]) -> None:
    """Initialize ZenML on given path.

    Args:
      path: Path to the repository.

    Raises:
        InitializationException: If the repo is already initialized.
    """
    if path is None:
        path = Path.cwd()

    with console.status(f"Initializing ZenML repository at {path}.\n"):
        try:
            Repository.initialize(root=path)
            declare(f"ZenML repository initialized at {path}.")
        except InitializationException as e:
            error(f"{e}")

    gc = GlobalConfiguration()
    declare(
        f"The local active profile was initialized to "
        f"'{gc.active_profile_name}' and the local active stack to "
        f"'{gc.active_stack_name}'. This local configuration will only take "
        f"effect when you're running ZenML from the initialized repository "
        f"root, or from a subdirectory. For more information on profile "
        f"and stack configuration, please visit "
        f"https://docs.zenml.io."
    )


def _delete_local_files(force_delete: bool = False) -> None:
    """Delete local files corresponding to the active stack.

    Args:
      force_delete: Whether to force delete the files."""
    if not force_delete:
        confirm = confirmation(
            "DANGER: This will completely delete metadata, artifacts and so on associated with all active stack components. \n\n"
            "Are you sure you want to proceed?"
        )
        if not confirm:
            declare("Aborting clean.")
            return

    repo = Repository()
    if repo.active_stack:
        stack_components = repo.active_stack.components
        for _, component in stack_components.items():
            local_path = component.local_path
            if local_path:
                for path in Path(local_path).iterdir():
                    if fileio.isdir(str(path)):
                        fileio.rmtree(str(path))
                    else:
                        fileio.remove(str(path))
                    warning(
                        f"Deleted `{path}`", Style(color="blue", italic=True)
                    )
    declare("Deleted all files relating to the local active stack.")


@cli.command("clean", hidden=True)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Don't ask for confirmation.",
)
@click.option(
    "--local",
    "-l",
    is_flag=True,
    default=False,
    help="Delete local files relating to the active stack.",
)
def clean(yes: bool = False, local: bool = False) -> None:
    """Delete all ZenML metadata, artifacts, profiles and stacks.

    This is a destructive operation, primarily intended for use in development.

    Args:
      yes (flag; default value = False): If you don't want a confirmation prompt.
      local (flag; default value = False): If you want to delete local files associated with the active stack.
    """
    if local:
        _delete_local_files(force_delete=yes)
        return

    if not yes:
        confirm = confirmation(
            "DANGER: This will completely delete all artifacts, metadata, stacks and profiles \n"
            "ever created during the use of ZenML. Pipelines and stack components running non-\n"
            "locally will still exist. Please delete those manually. \n\n"
            "Are you sure you want to proceed?"
        )

    if yes or confirm:
        # delete the .zen folder
        local_zen_repo_config = Path.cwd() / REPOSITORY_DIRECTORY_NAME
        if fileio.exists(str(local_zen_repo_config)):
            fileio.rmtree(str(local_zen_repo_config))
            declare(f"Deleted local ZenML config from {local_zen_repo_config}.")

        # delete the profiles (and stacks)
        global_zen_config = Path(get_global_config_directory())
        if fileio.exists(str(global_zen_config)):
            gc = GlobalConfiguration()
            for dir_name in fileio.listdir(str(global_zen_config)):
                if fileio.isdir(str(global_zen_config / str(dir_name))):
                    warning(
                        f"Deleting '{str(dir_name)}' directory from global config."
                    )
            fileio.rmtree(str(global_zen_config))
            declare(f"Deleted global ZenML config from {global_zen_config}.")
            fresh_gc = GlobalConfiguration(
                user_id=gc.user_id,
                analytics_opt_in=gc.analytics_opt_in,
                version=gc.version,
            )
            fresh_gc._add_and_activate_default_profile()
            declare(f"Reinitialized ZenML global config at {Path.cwd()}.")

    else:
        declare("Aborting clean.")


@cli.command("go")
def go() -> None:
    """Quickly explore ZenML with this walkthrough."""
    console.print(zenml_go_welcome_message, width=80)

    from zenml.config.global_config import GlobalConfiguration

    gc = GlobalConfiguration()
    if not gc.user_metadata:
        _prompt_email(gc)

    console.print(zenml_go_privacy_message, width=80)

    zenml_tutorial_path = os.path.join(os.getcwd(), "zenml_tutorial")

    if not os.path.isdir(zenml_tutorial_path):
        try:
            from git.repo.base import Repo
        except ImportError as e:
            logger.error(
                "At this point we would want to clone our tutorial repo onto "
                "your machine to let you dive right into our code. However, "
                "this machine has no installation of Git. Feel free to install "
                "git and rerun this command. Alternatively you can also "
                f"download the repo manually here: {TUTORIAL_REPO}."
            )
            raise GitNotFoundError(e)
        Repo.clone_from(TUTORIAL_REPO, zenml_tutorial_path)

    ipynb_files = [
        fi for fi in os.listdir(zenml_tutorial_path) if fi.endswith(".ipynb")
    ]
    console.print(zenml_go_notebook_tutorial_message(ipynb_files), width=80)

    subprocess.check_call(["jupyter", "notebook"], cwd=zenml_tutorial_path)


def _prompt_email(gc: GlobalConfiguration) -> None:
    """Ask the user to give their email address"""

    console.print(zenml_go_email_prompt, width=80)

    email = click.prompt(
        click.style("Email: ", fg="blue"), default="", show_default=False
    )
    if email:
        if len(email) > 0 and email.count("@") != 1:
            warning("That doesn't look like an email. Skipping ...")
        else:

            console.print(zenml_go_thank_you_message, width=80)

            gc.user_metadata = {"email": email}
            identify_user({"email": email})
