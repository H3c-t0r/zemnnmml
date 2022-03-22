#  Copyright (c) ZenML GmbH 2020. All Rights Reserved.
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

import getpass

import click

from zenml.cli.cli import cli
from zenml.cli.utils import confirmation, error, print_table
from zenml.console import console
from zenml.enums import SecretSchema, StackComponentType
from zenml.repository import Repository
from zenml.secret.base_secret import Secret
from zenml.secret.secret_schema_class_registry import SecretSchemaClassRegistry
from zenml.secrets_manager.base_secrets_manager import BaseSecretsManager


def pretty_print_secret(secret: Secret, hide_secret: bool = True) -> None:
    stack_dicts = []
    for key, value in secret.get_contents.items():
        stack_dicts.append(
            {
                "SECRET_NAME": secret.name,
                "SECRET_KEY": key,
                "SECRET_VALUE": "***" if hide_secret else value,
            }
        )
    print_table(stack_dicts)


# Secrets
@cli.group()
@click.pass_context
def secret(ctx: click.Context) -> None:
    """Secrets for storing key-value pairs for use in authentication."""
    # TODO [HIGH]: Ensure the stack actually contains an active secrets manager
    ctx.obj = Repository().active_stack.components.get(
        StackComponentType.SECRETS_MANAGER, None
    )


@secret.command("register")
@click.argument("name", type=click.STRING)
@click.option(
    "--schema",
    "-s",
    "secret_schema_name",
    help="A registered secret to create with a schema.",
    type=click.Choice(SecretSchema.value_list()),
)
@click.pass_obj
def register_secret(
    secrets_manager: "BaseSecretsManager",
    name: str,
    secret_schema_name: str,
) -> None:
    """Create a secret."""
    # TODO [HIGH]: Verify secret_name does not exist already
    # TODO [HIGH]: Allow passing in json/dict when registering a secret

    secret_contents = {}

    if secret_schema_name:
        secret_schema = SecretSchemaClassRegistry.get_class(
            secret_schema=secret_schema_name
        )
        secret_keys = [field for field in secret_schema.__fields__]

        click.echo(
            "You have supplied a secret_set_schema with predefined keys. "
            "You can fill these out sequentially now. Just press ENTER to skip"
            "optional secrets that you do not want to set"
        )
        for k in secret_keys:
            v = getpass.getpass(f"Secret value for {k}:")
            secret_contents[k] = v

        secret_schema_contents = secret_schema(**secret_contents)

        click.echo("The following secret will be registered.")

        secret = Secret(
            name=name,
            contents=secret_schema_contents,
        )
    else:
        click.echo(
            "You have not supplied a secret_set_schema with any"
            "predefined keys. Entering interactive mode:"
        )
        while True:
            k = click.prompt("Please enter a secret-key")
            secret_contents[k] = getpass.getpass(
                f"Please enter the secret_value " f"for the key [{k}]:"
            )

            if not click.confirm(
                "Do you want to add another key-value pair to this secret?"
            ):
                break

        click.echo("The following secret will be registered.")

        secret = Secret(name=name, contents=secret_contents)

    pretty_print_secret(secret=secret, hide_secret=True)

    with console.status(f"Saving secret set `{name}`..."):
        secrets_manager.register_secret(secret=secret)


@secret.command("get")
@click.argument("name", type=click.STRING)
@click.pass_obj
def get_secret(
    secrets_manager: "BaseSecretsManager",
    name: str,
) -> None:
    """Get a secret set, given its name."""
    # with console.status(f"Getting secret set `{name}`..."):
    try:
        secret = secrets_manager.get_secret(secret_name=name)
        pretty_print_secret(secret, hide_secret=False)
    except KeyError:
        error(f"Secret Set with name:`{name}` does not exist.")


@secret.command("list")
@click.pass_obj
def list_secret(secrets_manager: "BaseSecretsManager") -> None:
    """Get a list of all the keys to secrets sets in the store."""
    with console.status("Getting secret keys..."):
        secret_keys = secrets_manager.get_all_secret_keys()
        # TODO: [HIGH] implement as a table?
        console.print(secret_keys)


@secret.command("update")
@click.argument("name", type=click.STRING)
@click.pass_obj
def update_secret(secrets_manager: "BaseSecretsManager", name: str) -> None:
    """Update a secret set, given its name."""
    # TODO [HIGH] - Implement a fine grained User Interface for the update
    #  secrets method that allows for deleting, adding and modifying specific
    #  keys, pass in dict

    with console.status(f"Getting secret set `{name}`..."):
        try:
            secret = secrets_manager.get_secret(secret_name=name)
        except KeyError:
            error(f"Secret Set with name:`{name}` does not exist.")

    click.echo(
        "You will now have a chance to overwrite each secret "
        "one by one. Press enter to skip."
    )
    updated_contents = dict()
    for key, value in secret.get_contents.items():
        new_value = getpass.getpass(f"New value for " f"{key}:")
        if new_value:
            updated_contents[key] = new_value
        else:
            updated_contents[key] = value

    secret.contents = updated_contents

    pretty_print_secret(secret, hide_secret=True)

    with console.status(f"Updating secret set `{name}`..."):
        try:
            secrets_manager.update_secret(secret=secret)
            console.print(f"Secret with name '{name}' has been updated")
        except KeyError:
            error(f"Secret Set with name:`{name}` already exists.")


@secret.command("delete")
@click.argument("name", type=click.STRING)
@click.pass_obj
def delete_secret_set(
    secrets_manager: "BaseSecretsManager",
    name: str,
) -> None:
    """Delete a secret set."""
    confirmation_response = confirmation(
        f"This will delete the secret associated with `{name}`. "
        "Are you sure you want to proceed?"
    )
    if not confirmation_response:
        console.print("Aborting secret set deletion...")
    else:
        with console.status(f"Deleting secret `{name}`..."):
            try:
                secrets_manager.delete_secret(name)
                console.print(f"Deleted secret for `{name.upper()}`.")
            except KeyError:
                error(f"Secret with name:`{name}` already did not exist.")


@secret.command("cleanup")
@click.option(
    "--force",
    "-f",
    "force",
    is_flag=True,
    help="Force the deletion of all secrets",
    type=click.BOOL,
)
@click.pass_obj
def delete_all_secrets(
    secrets_manager: "BaseSecretsManager", force: bool
) -> None:
    """Delete a secret set."""
    confirmation_response = confirmation(
        "This will delete the all secrets. Are you sure you want to proceed?"
    )
    if not confirmation_response:
        console.print("Aborting secret set deletion...")
    else:
        with console.status("Deleting all secrets ..."):
            secrets_manager.delete_all_secrets(force=force)
            console.print("Deleted all secrets.")
