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
"""CLI functionality to interact with the ZenML Hub."""
import os
import shutil
import subprocess
import sys
from importlib.util import find_spec
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import uuid4

import click
import requests
from git import GitCommandError
from git.repo import Repo
from pydantic import BaseModel, ValidationError

from zenml.cli.cli import TagGroup, cli
from zenml.cli.utils import declare, error, print_table
from zenml.enums import CliCategories
from zenml.hub.config import get_settings
from zenml.logger import get_logger

logger = get_logger(__name__)

Json = Union[Dict[str, Any], List[Any], str, int, float, bool, None]

ZENML_HUB_INTERNAL_TAG_PREFIX = "zenml-"


class PluginBaseModel(BaseModel):
    """Base model for a plugin."""

    name: str
    description: Optional[str]
    version: Optional[str]
    release_notes: Optional[str]
    repository_url: str
    repository_subdirectory: Optional[str]
    repository_branch: Optional[str]
    repository_commit: Optional[str]
    tags: List[str]


class PluginRequestModel(PluginBaseModel):
    """Request model for a plugin."""


class PluginResponseModel(PluginBaseModel):
    """Response model for a plugin."""

    status: str
    version: str
    index_url: Optional[str]
    package_name: Optional[str]
    logo: Optional[str]
    requirements: Optional[List[str]]


def _hub_request(
    method: str,
    url: str,
    data: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[Json]:
    """Helper function to make a request to the hub."""
    session = requests.Session()

    # Define headers
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    auth_token = get_settings().AUTH_TOKEN
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    # Make the request
    response = session.request(
        method=method,
        url=url,
        data=data,
        headers=headers,
        params=params,
        verify=False,
        timeout=30,
    )

    # Parse and return the response
    response_json: Json = response.json() if response else None
    return response_json


def _list_plugins(**params: Any) -> List[PluginResponseModel]:
    """Helper function to list all plugins in the hub."""
    url = f"{get_settings().SERVER_URL}/plugins"
    response = _hub_request("GET", url, params=params)
    if not isinstance(response, list):
        return []
    return [PluginResponseModel.parse_obj(plugin) for plugin in response]


def _get_plugin(
    plugin_name: str, plugin_version: Optional[str] = None
) -> Optional[PluginResponseModel]:
    """Helper function to get a specfic plugin from the hub."""
    url = f"{get_settings().SERVER_URL}/plugins/{plugin_name}"
    if plugin_version:
        url += f"?version={plugin_version}"

    response = _hub_request("GET", url)
    try:
        return PluginResponseModel.parse_obj(response)
    except ValidationError:
        return None


def _create_plugin(
    plugin_request: PluginRequestModel, is_new_version: bool
) -> PluginResponseModel:
    """Helper function to create a plugin in the hub."""
    url = f"{get_settings().SERVER_URL}/plugins"
    if is_new_version:
        url += f"/{plugin_request.name}/versions"

    response = _hub_request("POST", url, data=plugin_request.json())

    try:
        return PluginResponseModel.parse_obj(response)
    except ValidationError:
        raise RuntimeError(
            f"Failed to create plugin {plugin_request.name}: {response}"
        )


def _stream_plugin_build_logs(plugin_name: str, plugin_version: str) -> None:
    """Helper function to stream the build logs of a plugin."""
    logs_url = (
        f"{get_settings().SERVER_URL}/plugins/{plugin_name}/versions/"
        f"{plugin_version}/logs"
    )
    found_logs = False
    with requests.get(logs_url, stream=True) as response:
        for line in response.iter_lines(chunk_size=None, decode_unicode=True):
            found_logs = True
            if line.startswith("Build failed"):
                error(line)
            else:
                logger.info(line)

    if not found_logs:
        logger.info(f"No logs found for plugin {plugin_name}:{plugin_version}")


def _is_plugin_installed(plugin_name: str) -> bool:
    """Helper function to check if a plugin is installed."""
    spec = find_spec(f"zenml.hub.{plugin_name}")
    return spec is not None


def _format_plugins_table(
    plugins: List[PluginResponseModel],
) -> List[Dict[str, str]]:
    """Helper function to format a list of plugins into a table."""
    plugins_table = []
    for plugin in plugins:
        if _is_plugin_installed(plugin.name):
            installed_icon = ":white_check_mark:"
        else:
            installed_icon = ":x:"
        plugins_table.append({"INSTALLED": installed_icon, **plugin.dict()})
    return plugins_table


def _plugin_display_name(plugin_name: str, version: Optional[str]) -> str:
    """Helper function to get the display name of a plugin.

    Args:
        plugin_name: Name of the plugin.
        version: Version of the plugin.

    Returns:
        Display name of the plugin.
    """
    if version:
        return f"{plugin_name}:{version}"
    return f"{plugin_name}:latest"


@cli.group(cls=TagGroup, tag=CliCategories.HUB)
def hub() -> None:
    """Interact with the ZenML Hub."""


@hub.command("list")
@click.option(
    "--mine",
    "-m",
    is_flag=True,
    help="List only plugins that you own.",
)
@click.option(
    "--installed",
    "-i",
    is_flag=True,
    help="List only plugins that are installed.",
)
def list_plugins(mine: bool, installed: bool) -> None:
    """List all plugins available on the hub."""
    plugins = _list_plugins(mine=mine)
    if not plugins:
        declare("No plugins found.")
    if installed:
        plugins = [
            plugin for plugin in plugins if _is_plugin_installed(plugin.name)
        ]
    plugins_table = _format_plugins_table(plugins)
    print_table(plugins_table)


@hub.command("install")
@click.argument("plugin_name", type=str, required=True)
@click.option(
    "--version",
    "-v",
    type=str,
    help="Version of the plugin to install.",
)
@click.option(
    "--no-deps",
    "--no-dependencies",
    is_flag=True,
    help="Do not install dependencies of the plugin.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Do not ask for confirmation before installing.",
)
def install_plugin(
    plugin_name: str,
    version: Optional[str] = None,
    no_deps: bool = False,
    yes: bool = False,
) -> None:
    """Install a plugin from the hub."""
    display_name = _plugin_display_name(plugin_name, version)

    # Get plugin from hub
    plugin = _get_plugin(plugin_name, version)
    if not plugin:
        error(f"Could not find plugin '{display_name}' on the hub.")

    # Check if plugin can be installed
    index_url = plugin.index_url
    package_name = plugin.package_name
    if not index_url or not package_name:
        error(f"Plugin '{display_name}' is not available for installation.")

    # Install plugin dependencies
    if not no_deps and plugin.requirements:
        requirements_str = " ".join(f"'{r}'" for r in plugin.requirements)

        if not yes:
            confirmation = click.confirm(
                f"Plugin '{display_name}' requires the following "
                f"packages to be installed: {requirements_str}. Do you want to "
                f"install them now?"
            )
            if not confirmation:
                error(
                    f"Plugin '{display_name}' cannot be installed "
                    "without the required packages."
                )

        logger.info(
            f"Installing requirements for plugin '{display_name}': "
            f"{requirements_str}..."
        )
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *plugin.requirements]
        )
        logger.info(
            f"Successfully installed requirements for plugin "
            f"'{display_name}'."
        )

    # pip install the wheel
    logger.info(
        f"Installing plugin '{display_name}' from "
        f"{index_url}{package_name}..."
    )
    install_call = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--index-url",
        index_url,
        package_name,
    ]
    if no_deps:
        install_call.append("--no-deps")
    subprocess.check_call(install_call)
    logger.info(f"Successfully installed plugin '{display_name}'.")


@hub.command("uninstall")
@click.argument("plugin_name", type=str, required=True)
@click.option(
    "--version",
    "-v",
    type=str,
    help="Version of the plugin to uninstall.",
)
def uninstall_plugin(plugin_name: str, version: Optional[str] = None) -> None:
    """Uninstall a plugin from the hub."""
    display_name = _plugin_display_name(plugin_name, version)

    # Get plugin from hub
    plugin = _get_plugin(plugin_name, version)
    if not plugin:
        error(f"Could not find plugin '{display_name}' on the hub.")

    # Check if plugin can be uninstalled
    package_name = plugin.package_name
    if not package_name:
        error(
            f"Plugin '{display_name}' is not available for " "uninstallation."
        )

    # pip uninstall the wheel
    logger.info(f"Uninstalling plugin '{display_name}'...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "uninstall", package_name, "-y"]
    )
    logger.info(f"Successfully uninstalled plugin '{display_name}'.")


@hub.command("pull")
@click.argument("plugin_name", type=str, required=True)
@click.option(
    "--version",
    "-v",
    type=str,
    help="Version of the plugin to pull.",
)
@click.option(
    "--output_dir",
    type=str,
    help="Output directory to pull the plugin to.",
)
def pull_plugin(
    plugin_name: str,
    version: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> None:
    """Pull a plugin from the hub."""
    display_name = _plugin_display_name(plugin_name, version)

    # Get plugin from hub
    plugin = _get_plugin(plugin_name, version)
    if not plugin:
        error(f"Could not find plugin '{display_name}' on the hub.")

    repo_url = plugin.repository_url
    subdir = plugin.repository_subdirectory
    commit = plugin.repository_commit

    # Clone the source repo
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), plugin_name)
    logger.info(f"Pulling plugin '{display_name}' to {output_dir}...")
    # If no subdir, we can clone directly into output_dir
    if not subdir:
        repo_path = plugin_dir = output_dir
    # Otherwise, we need to clone into a random dir and then move the subdir
    else:
        random_repo_name = f"_{uuid4()}"
        repo_path = os.path.abspath(
            os.path.join(os.getcwd(), random_repo_name)
        )
        plugin_dir = os.path.join(repo_path, subdir)

    # Clone the repo and move it to `output_dir`
    try:
        _clone_repo(url=repo_url, to_path=repo_path, commit=commit)
        shutil.move(plugin_dir, output_dir)
        logger.info(f"Successfully pulled plugin '{display_name}'.")
    except GitCommandError:
        error(
            f"Could not find commit '{commit}' in repository '{repo_url}' "
            f"of plugin '{display_name}'. This might happen if the owner "
            "of the plugin has force-pushed to the plugin repository. "
            "Please report this plugin version in the ZenML Hub or via "
            "Slack."
        )
    finally:
        shutil.rmtree(repo_path)


def _clone_repo(
    url: str,
    to_path: str,
    branch: Optional[str] = None,
    commit: Optional[str] = None,
) -> None:
    """Clone a repository and get the hash of the latest commit.

    Args:
        url: URL of the repository to clone.
        to_path: Path to clone the repository to.
        branch: Branch to clone. Defaults to "main".
        commit: Commit to checkout. If specified, the branch argument is
            ignored.
    """
    os.makedirs(os.path.basename(to_path), exist_ok=True)
    if commit:
        repo = Repo.clone_from(
            url=url,
            to_path=to_path,
            no_checkout=True,
        )
        repo.git.checkout(commit)
    else:
        repo = Repo.clone_from(
            url=url,
            to_path=to_path,
            branch=branch or "main",
        )


@hub.command("push")
@click.option(
    "--plugin_name",
    "-n",
    type=str,
    help=(
        "Name of the plugin to push. If not provided, the name will be asked "
        "for interactively."
    ),
)
@click.option(
    "--version",
    "-v",
    type=str,
    help=(
        "Version of the plugin to push. Can only be set if the plugin already "
        "exists. If not provided, the version will be autoincremented."
    ),
)
@click.option(
    "--release_notes",
    "-r",
    type=str,
    help="Release notes for the plugin version.",
)
@click.option(
    "--description",
    "-d",
    type=str,
    help="Description of the plugin.",
)
@click.option(
    "--repository_url",
    "-u",
    type=str,
    help="URL to the public Git repository containing the plugin source code.",
)
@click.option(
    "--repository_subdir",
    "-s",
    type=str,
    help="Subdirectory of the repository containing the plugin source code.",
)
@click.option(
    "--repository_branch",
    "-b",
    type=str,
    help="Branch to checkout from the repository.",
)
@click.option(
    "--repository_commit",
    "-c",
    type=str,
    help="Commit to checkout from the repository. Overrides --branch.",
)
@click.option(
    "tags",
    "--tag",
    "-t",
    type=str,
    multiple=True,
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Run the command in interactive mode.",
)
def push_plugin(
    plugin_name: Optional[str],
    version: Optional[str],
    release_notes: Optional[str],
    description: Optional[str],
    repository_url: Optional[str],
    repository_subdir: Optional[str],
    repository_branch: Optional[str],
    repository_commit: Optional[str],
    tags: List[str],
    interactive: bool,
) -> None:
    """Push a plugin to the hub."""
    # Validate that the plugin name is provided and available
    plugin_name, plugin_exists = _validate_plugin_name(
        plugin_name=plugin_name, interactive=interactive
    )

    # If the plugin exists, ask for version and release notes in interactive
    # mode.
    if plugin_exists and interactive:
        if not version:
            logger.info(
                "You are about to create a new version of plugin "
                f"'{plugin_name}'. By default, this will increment the minor "
                "version of the plugin. If you want to specify a different "
                "version, you can do so below. In that case, make sure that "
                "the version is of shape '<int>.<int>' and is higher than the "
                "current latest version of the plugin."
            )
            version = click.prompt("(Optional) plugin version", default="")
        if not release_notes:
            logger.info(
                f"You are about to create a new version of plugin "
                f"'{plugin_name}'. You can optionally provide release notes "
                "for this version below."
            )
            release_notes = click.prompt(
                "(Optional) release notes", default=""
            )

    # Raise an error if the plugin does not exist and a version is provided.
    elif not plugin_exists and version:
        error(
            "You cannot specify a version for a plugin that does not exist "
            "yet. Please remove the '--version' flag and try again."
        )

    # Clone the repo and validate the commit / branch / subdir / structure
    (
        repository_url,
        repository_commit,
        repository_branch,
        repository_subdir,
    ) = _validate_repository(
        url=repository_url,
        commit=repository_commit,
        branch=repository_branch,
        subdir=repository_subdir,
        interactive=interactive,
    )

    # In interactive mode, ask for a description if none is provided
    if interactive and not description:
        logger.info(
            "You can optionally provide a description for your plugin below. "
            "If not set, the first line of your README.md will be used."
        )
        description = click.prompt("(Optional) plugin description", default="")

    # Validate the tags
    tags = _validate_tags(tags=tags, interactive=interactive)

    # Make a create request to the hub
    plugin_request = PluginRequestModel(
        name=plugin_name,
        description=description,
        version=version,
        release_notes=release_notes,
        repository_url=repository_url,
        repository_subdirectory=repository_subdir,
        repository_branch=repository_branch,
        repository_commit=repository_commit,
        tags=tags,
    )
    plugin_response = _create_plugin(
        plugin_request=plugin_request,
        is_new_version=plugin_exists,
    )

    # Stream the build logs
    plugin_name = plugin_response.name
    plugin_version = plugin_response.version
    logger.info(
        "Thanks for submitting your plugin to the ZenML Hub. The plugin is now "
        "being built into an installable package. This may take a few minutes. "
        "To view the build logs, run "
        f"`zenml hub logs {plugin_name} --version {plugin_version}`."
    )


def _validate_plugin_name(
    plugin_name: Optional[str], interactive: bool
) -> Tuple[str, bool]:
    """Validate that the plugin name is provided and available.

    Args:
        plugin_name: The plugin name to validate.
        interactive: Whether to run in interactive mode.

    Returns:
        The validated plugin name, and whether the plugin already exists.
    """
    # Make sure the plugin name is provided.
    if not plugin_name:
        if not interactive:
            error("Plugin name not provided.")
        logger.info("Please enter a name for the plugin.")
        plugin_name = click.prompt("Plugin name")

    # Make sure the plugin name is valid.
    while True:
        if plugin_name:
            existing_plugin = _get_plugin(plugin_name)

            # If the plugin name is available, we're good.
            if not existing_plugin:
                return plugin_name, False

            # if the plugin already exists, make sure it's the user's plugin.
            my_plugins = _list_plugins(mine=True)
            for plugin in my_plugins:
                if plugin.name == plugin_name:
                    return plugin_name, True

        if not interactive:
            error("Plugin name not provided or not available.")
        logger.info(
            f"A plugin with name '{plugin_name}' already exists in the "
            "hub. Please choose a different name."
        )
        plugin_name = click.prompt("Plugin name")


def _validate_repository(
    url: Optional[str],
    commit: Optional[str],
    branch: Optional[str],
    subdir: Optional[str],
    interactive: bool,
) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """Validate the provided repository arguments.

    Args:
        url: The URL to the repository to clone.
        commit: The commit to checkout.
        branch: The branch to checkout. Will be ignored if commit is provided.
        subdir: The subdirectory in which the plugin is located.
        interactive: Whether to run in interactive mode.

    Returns:
        - The validated URL to the repository,
        - The cloned repository,
        - The path to the cloned repository.
    """
    while True:

        # Make sure the repository URL is provided.
        if not url:
            if not interactive:
                error("Repository URL not provided.")
            logger.info(
                "Please enter the URL to the public Git repository containing "
                "the plugin source code."
            )
            url = click.prompt("Repository URL")
        assert url is not None

        # In interactive mode, ask for the branch and commit if not provided
        if interactive and not branch and not commit:
            confirmation = click.confirm(
                "Do you want to use the latest commit from the 'main' branch "
                "of the repository?"
            )
            if not confirmation:
                confirmation = click.confirm(
                    "You can either use a specific commit or the latest commit "
                    "from one of your branches. Do you want to use a specific "
                    "commit?"
                )
                if confirmation:
                    logger.info("Please enter the SHA of the commit.")
                    commit = click.prompt("Repository commit")
                    branch = None
                else:
                    logger.info("Please enter the name of a branch.")
                    branch = click.prompt("Repository branch")
                    commit = None

        try:
            # Check if the URL/branch/commit are valid.
            repo_path = f"_{uuid4()}"
            _clone_repo(
                url=url,
                commit=commit,
                branch=branch,
                to_path=repo_path,
            )

            # Check if the subdir exists and has the correct structure.
            subdir = _validate_repository_subdir(
                repository_subdir=subdir,
                repo_path=repo_path,
                interactive=interactive,
            )

            return url, commit, branch, subdir

        except GitCommandError:
            repo_display_name = f"'{url}'"
            suggestion = "Please enter a valid repository URL"
            if commit:
                repo_display_name += f" (commit '{commit}')"
                suggestion += " and make sure the commit exists."
            elif branch:
                repo_display_name += f" (branch '{branch}')"
                suggestion += " and make sure the branch exists."
            else:
                suggestion += " and make sure the 'main' branch exists."
            msg = f"Could not clone repository from URL {repo_display_name}. "
            if not interactive:
                error(msg + suggestion)
            logger.info(msg + suggestion)
            url, branch, commit = None, None, None

        finally:
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path)


def _validate_repository_subdir(
    repository_subdir: Optional[str], repo_path: str, interactive: bool
) -> Optional[str]:
    """Validate the provided repository subdirectory.

    Args:
        repository_subdir: The subdirectory to validate.
        repo_path: The path to the repository to validate the subdirectory in.
        interactive: Whether to run in interactive mode.

    Returns:
        The validated subdirectory.
    """
    while True:
        # In interactive mode, ask for the subdirectory if not provided
        if interactive and not repository_subdir:
            confirmation = click.confirm(
                "Is the plugin source code in the root of the repository?"
            )
            if not confirmation:
                logger.info(
                    "Please enter the subdirectory of the repository "
                    "containing the plugin source code."
                )
                repository_subdir = click.prompt("Repository subdirectory")

        # If a subdir was provided, make sure it exists
        if repository_subdir:
            subdir_path = os.path.join(repo_path, repository_subdir)
            if not os.path.exists(subdir_path):
                if not interactive:
                    error("Repository subdirectory does not exist.")
                logger.info(
                    f"Subdirectory '{repository_subdir}' does not exist in the "
                    f"repository."
                )
                logger.info("Please enter a valid subdirectory.")
                repository_subdir = click.prompt(
                    "Repository subdirectory", default=""
                )
                continue

        # Check if the plugin structure is valid.
        if repository_subdir:
            plugin_path = os.path.join(repo_path, repository_subdir)
        else:
            plugin_path = repo_path
        try:
            _validate_repository_structure(plugin_path)
            return repository_subdir
        except ValueError as e:
            msg = (
                f"Plugin code structure at {repository_subdir} is invalid: "
                f"{str(e)}"
            )
            if not interactive:
                error(str(e))
            logger.info(msg)
            logger.info("Please enter a valid subdirectory.")
            repository_subdir = click.prompt("Repository subdirectory")


def _validate_repository_structure(plugin_root: str) -> None:
    """Validate the repository structure of a submitted ZenML Hub plugin.

    We expect the following structure:
    - README.md
    - requirements.txt
    - src/

    Args:
        plugin_root: Root directory of the plugin.

    Raises:
        ValueError: If the repo does not have the correct structure.
    """
    # README.md exists.
    readme_path = os.path.join(plugin_root, "README.md")
    if not os.path.exists(readme_path):
        raise ValueError("README.md not found")

    # requirements.txt exists.
    requirements_path = os.path.join(plugin_root, "requirements.txt")
    if not os.path.exists(requirements_path):
        raise ValueError("requirements.txt not found")

    # src/ exists.
    src_path = os.path.join(plugin_root, "src")
    if not os.path.exists(src_path):
        raise ValueError("src/ not found")


def _validate_tags(tags: List[str], interactive: bool) -> List[str]:
    """Validate the provided tags.

    Args:
        tags: The tags to validate.

    Returns:
        The validated tags.
    """
    if not tags:
        if not interactive:
            return []

        # In interactive mode, ask for tags if none were provided.
        return _ask_for_tags()

    # If tags were provided, print a warning if any of them is invalid.
    for tag in tags:
        if tag.startswith(ZENML_HUB_INTERNAL_TAG_PREFIX):
            logger.warning(
                f"Tag '{tag}' will be ignored because it starts with "
                f"disallowed prefix '{ZENML_HUB_INTERNAL_TAG_PREFIX}'."
            )
    return tags


def _ask_for_tags() -> List[str]:
    """Repeatedly ask the user for tags to assign to the plugin.

    Returns:
        A list of tags.
    """
    tags: List[str] = []
    while True:
        tag = click.prompt(
            "(Optional) enter tags you want to assign to the plugin.",
            default="",
        )
        if not tag:
            return tags
        if tag.startswith(ZENML_HUB_INTERNAL_TAG_PREFIX):
            logger.warning(
                "User-defined tags may not start with "
                f"'{ZENML_HUB_INTERNAL_TAG_PREFIX}'."
            )
        else:
            tags.append(tag)


@hub.command("logs")
@click.argument("plugin_name", type=str, required=True)
@click.option(
    "--version",
    "-v",
    type=str,
    help="Version of the plugin to pull.",
)
def get_logs(plugin_name: str, version: Optional[str] = None) -> None:
    display_name = _plugin_display_name(plugin_name, version)

    # Get the plugin from the hub
    plugin = _get_plugin(plugin_name=plugin_name, plugin_version=version)
    if not plugin:
        error(f"Could not find plugin '{display_name}' on the hub.")

    # Stream the logs
    _stream_plugin_build_logs(
        plugin_name=plugin_name, plugin_version=plugin.version
    )
