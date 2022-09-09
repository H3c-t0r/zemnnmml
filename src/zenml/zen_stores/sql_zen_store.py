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
"""SQL Zen Store implementation."""

import os
from pathlib import Path, PurePath
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Type, Union
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError, NoResultFound
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.sql.expression import Select, SelectOfScalar

from zenml.config.store_config import StoreConfiguration
from zenml.enums import ExecutionStatus, StackComponentType, StoreType
from zenml.exceptions import EntityExistsError, StackExistsError
from zenml.io import fileio
from zenml.logger import get_logger
from zenml.metadata_stores.sqlite_metadata_store import SQLiteMetadataStore
from zenml.models import (
    ComponentModel,
    FlavorModel,
    PipelineRunModel,
    ProjectModel,
    RoleAssignmentModel,
    RoleModel,
    StackModel,
    TeamModel,
    UserModel,
)
from zenml.models.code_models import CodeRepositoryModel
from zenml.models.pipeline_models import (
    ArtifactModel,
    PipelineModel,
    StepRunModel,
)
from zenml.stack.flavor_registry import flavor_registry
from zenml.utils import io_utils, uuid_utils
from zenml.zen_stores.base_zen_store import DEFAULT_USERNAME, BaseZenStore
from zenml.zen_stores.schemas import (
    CodeRepositorySchema,
    FlavorSchema,
    PipelineRunSchema,
    PipelineSchema,
    ProjectSchema,
    RoleSchema,
    StackComponentSchema,
    StackSchema,
    TeamAssignmentSchema,
    TeamRoleAssignmentSchema,
    TeamSchema,
    UserRoleAssignmentSchema,
    UserSchema,
)

# Enable SQL compilation caching to remove the https://sqlalche.me/e/14/cprf
# warning
SelectOfScalar.inherit_cache = True
Select.inherit_cache = True

logger = get_logger(__name__)

ZENML_SQLITE_DB_FILENAME = "zenml.db"


class SqlZenStoreConfiguration(StoreConfiguration):
    """SQL ZenML store configuration.

    Attributes:
        _sql_kwargs: Additional keyword arguments to pass to the SQLAlchemy
            engine.
    """

    type: StoreType = StoreType.SQL
    _sql_kwargs: Dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        """Initializes the SQL ZenML store configuration.

        The constructor collects all extra fields into a private _sql_kwargs
        attribute.

        Args:
            **kwargs: Keyword arguments to pass to the Pydantic constructor.
        """
        # Create a list of fields that are in the Pydantic schema
        field_names = {
            field.alias
            for field in self.__fields__.values()
            if field.alias != "_sql_kwargs"
        }

        sql_kwargs: Dict[str, Any] = {}
        for field_name in list(kwargs):
            if field_name not in field_names:
                # Remove fields that are not in the Pydantic schema and add them
                # to the sql_kwargs dict
                sql_kwargs[field_name] = kwargs.get(field_name)
        super().__init__(**kwargs)
        self._sql_kwargs = sql_kwargs


class SqlZenStore(BaseZenStore):
    """Store Implementation that uses SQL database backend."""

    config: SqlZenStoreConfiguration
    TYPE: ClassVar[StoreType] = StoreType.SQL
    CONFIG_TYPE: ClassVar[Type[StoreConfiguration]] = SqlZenStoreConfiguration

    _engine: Optional[Engine] = None
    _metadata_store: Optional[SQLiteMetadataStore] = None

    def _initialize(self) -> None:
        """Initialize the SQL store."""
        logger.debug("Initializing SqlZenStore at %s", self.config.url)

        local_path = self.get_path_from_url(self.config.url)
        if local_path:
            io_utils.create_dir_recursive_if_not_exists(str(local_path.parent))

        metadata_store_path = os.path.join(
            os.path.dirname(str(local_path)), "metadata.db"
        )
        self._metadata_store = SQLiteMetadataStore(uri=metadata_store_path)

        self._engine = create_engine(self.config.url, **self.config._sql_kwargs)
        SQLModel.metadata.create_all(self._engine)

    @property
    def engine(self) -> Engine:
        """The SQLAlchemy engine.

        Returns:
            The SQLAlchemy engine.

        Raises:
            ValueError: If the store is not initialized.
        """
        if not self._engine:
            raise ValueError("Store not initialized")
        return self._engine

    @property
    def metadata_store(self) -> SQLiteMetadataStore:
        """The metadata store.

        Returns:
            The metadata store.

        Raises:
            ValueError: If the store is not initialized.
        """
        if not self._metadata_store:
            raise ValueError("Store not initialized")
        return self._metadata_store

    # Static methods:

    @staticmethod
    def get_path_from_url(url: str) -> Optional[Path]:
        """Get the local path from a URL, if it points to a local sqlite file.

        This method first checks that the URL is a valid SQLite URL, which is
        backed by a file in the local filesystem. All other types of supported
        SQLAlchemy connection URLs are considered non-local and won't return
        a valid local path.

        Args:
            url: The URL to get the path from.

        Returns:
            The path extracted from the URL, or None, if the URL does not
            point to a local sqlite file.
        """
        url = SqlZenStore.validate_url(url)
        if not url.startswith("sqlite:///"):
            return None
        url = url.replace("sqlite:///", "")
        return Path(url)

    @staticmethod
    def get_local_url(path: str) -> str:
        """Get a local SQL url for a given local path.

        Args:
            path: The path to the local sqlite file.

        Returns:
            The local SQL url for the given path.
        """
        return f"sqlite:///{path}/{ZENML_SQLITE_DB_FILENAME}"

    @staticmethod
    def validate_url(url: str) -> str:
        """Check if the given url is valid.

        Args:
            url: The url to check.

        Returns:
            The validated url.

        Raises:
            ValueError: If the url is not valid.
        """
        try:
            make_url(url)
        except ArgumentError as e:
            raise ValueError(
                "Invalid SQLAlchemy URL `%s`: %s. Check the SQLAlchemy "
                "documentation at https://docs.sqlalchemy.org/en/14/core/engines.html#database-urls "
                "for the correct format.",
                url,
                str(e),
            )
        return url

    @classmethod
    def copy_local_store(
        cls,
        config: StoreConfiguration,
        path: str,
        load_config_path: Optional[PurePath] = None,
    ) -> StoreConfiguration:
        """Copy a local store to a new location.

        Use this method to create a copy of a store database to a new location
        and return a new store configuration pointing to the database copy. This
        only applies to stores that use the local filesystem to store their
        data. Calling this method for remote stores simply returns the input
        store configuration unaltered.

        Args:
            config: The configuration of the store to copy.
            path: The new local path where the store DB will be copied.
            load_config_path: path that will be used to load the copied store
                database. This can be set to a value different from `path`
                if the local database copy will be loaded from a different
                environment, e.g. when the database is copied to a container
                image and loaded using a different absolute path. This will be
                reflected in the paths and URLs encoded in the copied store
                configuration.

        Returns:
            The store configuration of the copied store.
        """
        config_copy = config.copy()

        local_path = cls.get_path_from_url(config.url)
        if not local_path:
            # this is not a configuration backed by a local filesystem
            return config_copy
        io_utils.create_dir_recursive_if_not_exists(path)
        fileio.copy(
            str(local_path), str(Path(path) / local_path.name), overwrite=True
        )
        if load_config_path:
            config_copy.url = cls.get_local_url(str(load_config_path))
        else:
            config_copy.url = cls.get_local_url(path)

        return config_copy

    # Public interface:

    # .--------.
    # | STACKS |
    # '--------'

    @property
    def stacks_empty(self) -> bool:
        """Check if the store is empty (no stacks are configured).

        The implementation of this method should check if the store is empty
        without having to load all the stacks from the persistent storage.

        Returns:
            True if the store is empty, False otherwise.
        """
        with Session(self.engine) as session:
            return not session.exec(select(StackSchema)).first()

    @property
    def stack_names(self) -> List[str]:
        """Names of all stacks registered in this ZenStore.

        Returns:
            List of all stack names.
        """
        with Session(self.engine) as session:
            return [s.name for s in session.exec(select(StackSchema))]

    def _list_stacks(
        self,
        project_name_or_id: Union[str, UUID],
        user_id: Optional[UUID] = None,
        name: Optional[str] = None,
        is_shared: Optional[bool] = None,
    ) -> List[StackModel]:
        """List all stacks within the filter.

        Args:
            project_name_or_id: Name or Id of the Project containing the stack
            user_id: Optionally filter stack components by the owner
            name: Optionally filter stack component by name
            is_shared: Optionally filter out stack component by the `is_shared`
                       flag
        Returns:
            A list of all stacks.

        Raises:
            KeyError: If the project does not exist.
        """
        with Session(self.engine) as session:
            project = self._get_project_schema(project_name_or_id)

            # Get a list of all stacks
            query = select(StackSchema).where(
                StackSchema.project_id == project.id
            )
            # TODO: prettify
            if user_id:
                query = query.where(StackSchema.owner == user_id)
            if name:
                query = query.where(StackSchema.name == name)
            if is_shared is not None:
                query = query.where(StackSchema.is_shared == is_shared)
            stacks = session.exec(query).all()

            return [stack.to_model() for stack in stacks]

    def _get_stack(self, stack_id: UUID) -> StackModel:
        """Get a stack by id.

        Args:
            stack_id: The id of the stack to get.

        Returns:
            The stack with the given id.
        """
        with Session(self.engine) as session:
            stack = session.exec(
                select(StackSchema).where(StackSchema.id == stack_id)
            ).first()

            if stack is None:
                raise KeyError(f"Stack with ID {stack_id} not found.")
            return stack.to_model()

    def _register_stack(
        self,
        user_id: UUID,
        project_name_or_id: Union[str, UUID],
        stack: StackModel,
    ) -> StackModel:
        """Register a new stack.

        Args:
            stack: The stack to register.
            user_id: The user that is registering this stack
            project_name_or_id: Name or Id of the Project containing the stack

        Returns:
            The registered stack.

        Raises:
            StackExistsError: In case a stack with that name is already owned
                by this user on this project.
        """
        with Session(self.engine) as session:
            project = self._get_project_schema(project_name_or_id)
            # Check if stack with the domain key (name, project, owner) already
            #  exists
            existing_stack = session.exec(
                select(StackSchema)
                .where(StackSchema.name == stack.name)
                .where(StackSchema.project_id == project.id)
                .where(StackSchema.owner == user_id)
            ).first()
            # TODO: verify if is_shared status needs to be checked here
            if existing_stack is not None:
                raise StackExistsError(
                    f"Unable to register stack with name "
                    f"'{stack.name}': Found "
                    f"existing stack with this name. in the project for "
                    f"this user."
                )

            # Get the Schemas of all components mentioned
            filters = [
                (StackComponentSchema.id == c.id)
                for c in stack.components.values()
            ]

            defined_components = session.exec(
                select(StackComponentSchema).where(or_(*filters))
            ).all()

            # Create the stack
            stack_in_db = StackSchema.from_create_model(
                project_id=project.id,
                user_id=user_id,
                defined_components=defined_components,
                stack=stack,
            )
            session.add(stack_in_db)
            session.commit()

            return stack_in_db.to_model()

    def _update_stack(self, stack: StackModel) -> StackModel:
        """Update an existing stack.

        Args:
            stack: The stack to update.

        Returns:
            The updated stack.
        """
        with Session(self.engine) as session:
            # Check if stack with the domain key (name, project, owner) already
            #  exists
            existing_stack = session.exec(
                select(StackSchema).where(StackSchema.id == stack.id)
            ).first()

            if existing_stack is None:
                raise KeyError(
                    f"Unable to update stack with id "
                    f"'{stack.id}': Found no"
                    f"existing stack with this id."
                )

            # Get the Schemas of all components mentioned
            filters = [
                (StackComponentSchema.id == c.id)
                for c in stack.components.values()
            ]

            defined_components = session.exec(
                select(StackComponentSchema).where(or_(*filters))
            ).all()

            existing_stack.from_update_model(
                stack=stack, defined_components=defined_components
            )
            session.add(existing_stack)
            session.commit()

            return existing_stack.to_model()

    def _delete_stack(self, stack_id: UUID) -> None:
        """Delete a stack.

        Args:
            stack_id: The id of the stack to delete.
        """
        with Session(self.engine) as session:
            try:
                stack = session.exec(
                    select(StackSchema).where(StackSchema.id == stack_id)
                ).one()
                session.delete(stack)
            except NoResultFound as error:
                raise KeyError from error

            session.commit()

    #  .-----------------.
    # | STACK COMPONENTS |
    # '------------------'

    def _list_stack_components(
        self,
        project_name_or_id: Union[str, UUID],
        type: Optional[str] = None,
        flavor_name: Optional[str] = None,
        user_id: Optional[UUID] = None,
        name: Optional[str] = None,
        is_shared: Optional[bool] = None,
    ) -> List[ComponentModel]:
        """List all stack components within the filter.

        Args:
            project_name_or_id: Id or name of the Project containing the stack
                                components
            type: Optionally filter by type of stack component
            flavor_name: Optionally filter by flavor
            user_id: Optionally filter stack components by the owner
            name: Optionally filter stack component by name
            is_shared: Optionally filter out stack component by the `is_shared`
                       flag

        Returns:
            All stack components currently registered.
        """
        with Session(self.engine) as session:
            project = self._get_project_schema(project_name_or_id)

            # Get a list of all stacks
            query = select(StackComponentSchema).where(
                StackComponentSchema.project_id == project.id
            )
            # TODO: [server] prettify this
            if type:
                query = query.where(StackComponentSchema.type == type)
            if flavor_name:
                query = query.where(
                    StackComponentSchema.flavor_name == flavor_name
                )
            if user_id:
                query = query.where(StackComponentSchema.owner == user_id)
            if name:
                query = query.where(StackComponentSchema.name == name)
            if is_shared is not None:
                query = query.where(StackComponentSchema.is_shared == is_shared)

            list_of_stack_components_in_db = session.exec(query).all()

        return [comp.to_model() for comp in list_of_stack_components_in_db]

    def _get_stack_component(self, component_id: UUID) -> ComponentModel:
        """Get a stack component by id.

        Args:
            component_id: The id of the stack component to get.

        Returns:
            The stack component with the given id.
        """
        with Session(self.engine) as session:
            stack_component = session.exec(
                select(StackComponentSchema).where(
                    StackComponentSchema.id == component_id
                )
            ).first()

        return stack_component.to_model()

    def _register_stack_component(
        self,
        user_id: UUID,
        project_name_or_id: Union[str, UUID],
        component: ComponentModel,
    ) -> ComponentModel:
        """Create a stack component.

        Args:
            user_id: The user that created the stack component.
            project_name_or_id: Name or Id of the Project the stack component
                                would be created in
            component: The stack component to create.

        Returns:
            The created stack component.
        """
        with Session(self.engine) as session:
            project = self._get_project_schema(project_name_or_id)

            # TODO: [server] verify that this logic is already handled at repo
            #                level
            # # Check if component with the domain key (name, project, owner) already
            # #  exists
            # existing_component = session.exec(
            #     select(StackComponentSchema)
            #     .where(StackComponentSchema.name == component.name)
            #     .where(StackComponentSchema.project_id == project_id)
            #     .where(StackComponentSchema.owner == user_id)
            #     .where(StackComponentSchema.type == component.type)
            # ).first()
            #
            # if existing_component is not None:
            #     raise StackComponentExistsError(
            #         f"Unable to register component with name "
            #         f"'{component.name}': Found "
            #         f"existing component with this name. in the project for "
            #         f"this user."
            #     )

            # Create the component
            component_in_db = StackComponentSchema.from_create_model(
                user_id=user_id, project_id=project.id, component=component
            )

            session.add(component_in_db)
            session.commit()

            return component_in_db.to_model()

    def _update_stack_component(
        self, component_id: UUID, component: ComponentModel
    ) -> ComponentModel:
        """Update an existing stack component.

        Args:
            component: The stack component to use for the update.

        Returns:
            The updated stack component.
        """
        with Session(self.engine) as session:
            existing_component = session.exec(
                select(StackComponentSchema).where(
                    StackComponentSchema.id == component_id
                )
            ).first()

            # TODO: verify if is_shared status needs to be checked here
            if existing_component is None:
                raise KeyError(
                    f"Unable to update component with id "
                    f"'{component.id}': Found no"
                    f"existing component with this id."
                )

            existing_component.from_update_model(component=component)
            session.add(existing_component)
            session.commit()

            return existing_component.to_model()

    def _delete_stack_component(self, component_id: UUID) -> None:
        """Delete a stack component.

        Args:
            component_id: The id of the stack component to delete.

        Raises:
            KeyError: if the stack component doesn't exist.
        """
        with Session(self.engine) as session:
            try:
                stack_component = session.exec(
                    select(StackComponentSchema).where(
                        StackComponentSchema.id == component_id
                    )
                ).one()
                session.delete(stack_component)
            except NoResultFound as error:
                raise KeyError from error

            session.commit()

    def _get_stack_component_side_effects(
        self,
        component_id: UUID,
        run_id: UUID,
        pipeline_id: UUID,
        stack_id: UUID,
    ) -> Dict[Any, Any]:
        """Get the side effects of a stack component.

        Args:
            component_id: The id of the stack component to get side effects for.
            run_id: The id of the run to get side effects for.
            pipeline_id: The id of the pipeline to get side effects for.
            stack_id: The id of the stack to get side effects for.
        """
        # TODO: implement this

    def _list_stack_component_types(self) -> List[str]:
        """List all stack component types.

        Returns:
            A list of all stack component types.
        """
        # TODO: This does not belong in the Zen Store
        return StackComponentType.values()

    def _list_stack_component_flavors_by_type(
        self,
        component_type: StackComponentType,
    ) -> List[FlavorModel]:
        """List all stack component flavors by type.

        Args:
            component_type: The stack component for which to get flavors.

        Returns:
            List of stack component flavors.
        """

        # List all the flavors of the component type
        zenml_flavors = [
            f
            for f in flavor_registry.get_flavors_by_type(
                component_type=component_type
            ).values()
        ]

        custom_flavors = self.get_flavors_by_type(component_type=component_type)

        return zenml_flavors + custom_flavors

    #  .------.
    # | USERS |
    # '-------'

    @property
    def active_user_name(self) -> str:
        """Gets the active username.

        Returns:
            The active username.
        """
        return DEFAULT_USERNAME

    def _list_users(self) -> List[UserModel]:
        """List all users.

        Returns:
            A list of all users.
        """
        with Session(self.engine) as session:
            users = session.exec(select(UserSchema)).all()

        return [user.to_model() for user in users]

    def _create_user(self, user: UserModel) -> UserModel:
        """Creates a new user.

        Args:
            user: User to be created.

        Returns:
            The newly created user.

        Raises:
            EntityExistsError: If a user with the given name already exists.
        """
        with Session(self.engine) as session:
            # Check if user with the given name already exists
            existing_user = session.exec(
                select(UserSchema).where(UserSchema.name == user.name)
            ).first()
            if existing_user is not None:
                raise EntityExistsError(
                    f"Unable to create user with name '{user.name}': "
                    f"Found existing user with this name."
                )

            # Create the user
            new_user = UserSchema.from_create_model(user)
            session.add(new_user)
            session.commit()

            # After committing the model, sqlmodel takes care of updating the
            # object with id, created_at, etc ...

            return new_user.to_model()

    def _get_user(self, user_name_or_id: UUID) -> UserModel:
        """Gets a specific user.

        Args:
            user_name_or_id: The name or ID of the user to get.

        Returns:
            The requested user, if it was found.

        Raises:
            KeyError: If no user with the given name or ID exists.
        """
        user = self._get_schema_by_name_or_id(
            object_name_or_id=user_name_or_id,
            schema_class=UserSchema,
            schema_name="user",
        )
        return user.to_model()

    def _update_user(self, user_id: UUID, user: UserModel) -> UserModel:
        """Updates an existing user.

        Args:
            user_id: The ID of the user to update.
            user: The User model to use for the update.

        Returns:
            The updated user.

        Raises:
            KeyError: If no user with the given name exists.
        """
        with Session(self.engine) as session:
            existing_user = session.exec(
                select(UserSchema).where(UserSchema.id == user_id)
            ).first()
            if existing_user is None:
                raise KeyError(
                    f"Unable to update user with id '{user_id}': "
                    "No user found with this id."
                )
            existing_user.from_update_model(user)
            session.add(existing_user)
            session.commit()
            return existing_user.to_model()

    def _delete_user(self, user_id: UUID) -> None:
        """Deletes a user.

        Args:
            user_id: The ID of the user to delete.

        Raises:
            KeyError: If no user with the given name exists.
        """
        with Session(self.engine) as session:
            user = session.exec(
                select(UserSchema).where(UserSchema.id == user_id)
            ).first()
            if user is None:
                raise KeyError(
                    f"Unable to delete user with id '{user_id}': "
                    "No user found with this id."
                )
            session.delete(user)
            session.commit()

    def get_invite_token(self, user_id: UUID) -> str:
        """Gets an invite token for a user.

        Args:
            user_id: ID of the user.

        Returns:
            The invite token for the specific user.
        """
        raise NotImplementedError()  # TODO

    def invalidate_invite_token(self, user_id: UUID) -> None:
        """Invalidates an invite token for a user.

        Args:
            user_id: ID of the user.
        """
        raise NotImplementedError()  # TODO

    #  .------.
    # | TEAMS |
    # '-------'

    def _list_teams(self) -> List[TeamModel]:
        """List all teams.

        Returns:
            A list of all teams.
        """
        with Session(self.engine) as session:
            teams = session.exec(select(TeamSchema)).all()
            return [team.to_model() for team in teams]

    def _create_team(self, team: TeamModel) -> TeamModel:
        """Creates a new team.

        Args:
            team: The team model to create.

        Returns:
            The newly created team.

        Raises:
            EntityExistsError: If a team with the given name already exists.
        """
        with Session(self.engine) as session:
            # Check if team with the given name already exists
            existing_team = session.exec(
                select(TeamSchema).where(TeamSchema.name == team.name)
            ).first()
            if existing_team is not None:
                raise EntityExistsError(
                    f"Unable to create team with name '{team.name}': "
                    f"Found existing team with this name."
                )

            # Create the team
            new_team = TeamSchema.from_create_model(team)
            session.add(new_team)
            session.commit()

            # After committing the model, sqlmodel takes care of updating the
            # object with id, created_at, etc ...

            return new_team.to_model()

    def _get_team(self, team_name_or_id: UUID) -> TeamModel:
        """Gets a specific team.

        Args:
            team_name_or_id: Name or ID of the team to get.

        Returns:
            The requested team.

        Raises:
            KeyError: If no team with the given name or ID exists.
        """
        team = self._get_schema_by_name_or_id(
            object_name_or_id=team_name_or_id,
            schema_class=TeamSchema,
            schema_name="team",
        )
        return team.to_model()

    def _delete_team(self, team_id: UUID) -> None:
        """Deletes a team.

        Args:
            team_id: ID of the team to delete.

        Raises:
            KeyError: If no team with the given ID exists.
        """
        with Session(self.engine) as session:
            team = session.exec(
                select(TeamSchema).where(TeamSchema.id == team_id)
            ).first()
            if team is None:
                raise KeyError(
                    f"Unable to delete team with id '{team_id}': "
                    "No team found with this id."
                )
            session.delete(team)
            session.commit()

    def add_user_to_team(self, user_id: UUID, team_id: UUID) -> None:
        """Adds a user to a team.

        Args:
            user_id: ID of the user to add to the team.
            team_id: ID of the team to which to add the user to.

        Raises:
            KeyError: If the team or user does not exist.
            EntityExistsError: If the user is already a member of the team.
        """
        with Session(self.engine) as session:
            # Check if team with the given ID exists
            team = session.exec(
                select(TeamSchema).where(TeamSchema.id == team_id)
            ).first()
            if team is None:
                raise KeyError(
                    f"Unable to add user with id '{user_id}' to team with id "
                    f"'{team_id}': No team found with this id."
                )

            # Check if user with the given ID exists
            user = session.exec(
                select(UserSchema).where(UserSchema.id == user_id)
            ).first()
            if user is None:
                raise KeyError(
                    f"Unable to add user with id '{user_id}' to team with id "
                    f"'{team_id}': No user found with this id."
                )

            # Check if user is already in the team
            existing_user_in_team = session.exec(
                select(TeamAssignmentSchema)
                .where(TeamAssignmentSchema.user_id == user_id)
                .where(TeamAssignmentSchema.team_id == team_id)
            ).first()
            if existing_user_in_team is not None:
                raise EntityExistsError(
                    f"Unable to add user with id '{user_id}' to team with id "
                    f"'{team_id}': User is already in the team."
                )

            # Add user to team
            team.users = team.users + [user]
            session.add(team)
            session.commit()

    def remove_user_from_team(self, user_id: UUID, team_id: UUID) -> None:
        """Removes a user from a team.

        Args:
            user_id: ID of the user to remove from the team.
            team_id: ID of the team from which to remove the user.

        Raises:
            KeyError: If the team or user does not exist.
        """
        with Session(self.engine) as session:
            # Check if team with the given ID exists
            team = session.exec(
                select(TeamSchema).where(TeamSchema.id == team_id)
            ).first()
            if team is None:
                raise KeyError(
                    f"Unable to remove user with id '{user_id}' from team with "
                    f"id '{team_id}': No team found with this id."
                )

            # Check if user with the given ID exists
            user = session.exec(
                select(UserSchema).where(UserSchema.id == user_id)
            ).first()
            if user is None:
                raise KeyError(
                    f"Unable to remove user with id '{user_id}' from team with "
                    f"id '{team_id}': No user found with this id."
                )

            # Remove user from team
            team.users = [user_ for user_ in team.users if user_.id != user_id]
            session.add(team)
            session.commit()

    def get_users_for_team(self, team_id: UUID) -> List[UserModel]:
        """Fetches all users of a team.

        Args:
            team_id: The ID of the team for which to get users.

        Returns:
            A list of all users that are part of the team.

        Raises:
            KeyError: If no team with the given ID exists.
        """
        with Session(self.engine) as session:
            team = session.exec(
                select(TeamSchema).where(TeamSchema.id == team_id)
            ).first()
            if team is None:
                raise KeyError(
                    f"Unable to get users for team with id '{team_id}': "
                    "No team found with this id."
                )
            return [user.to_model() for user in team.users]

    def get_teams_for_user(self, user_id: UUID) -> List[TeamModel]:
        """Fetches all teams for a user.

        Args:
            user_id: The ID of the user for which to get all teams.

        Returns:
            A list of all teams that the user is part of.

        Raises:
            KeyError: If no user with the given ID exists.
        """
        with Session(self.engine) as session:
            user = session.exec(
                select(UserSchema).where(UserSchema.id == user_id)
            ).first()
            if user is None:
                raise KeyError(
                    f"Unable to get teams for user with id '{user_id}': "
                    "No user found with this id."
                )
            return [team.to_model() for team in user.teams]

    #  .------.
    # | ROLES |
    # '-------'

    def _list_roles(self) -> List[RoleModel]:
        """List all roles.

        Returns:
            A list of all roles.
        """
        with Session(self.engine) as session:
            roles = session.exec(select(RoleSchema)).all()

        return [role.to_model() for role in roles]

    def _create_role(self, role: RoleModel) -> RoleModel:
        """Creates a new role.

        Args:
            role: The role model to create.

        Returns:
            The newly created role.

        Raises:
            EntityExistsError: If a role with the given name already exists.
        """
        with Session(self.engine) as session:
            # Check if role with the given name already exists
            existing_role = session.exec(
                select(RoleSchema).where(RoleSchema.name == role.name)
            ).first()
            if existing_role is not None:
                raise EntityExistsError(
                    f"Unable to create role '{role.name}': Role already exists."
                )

            # Create role
            role_schema = RoleSchema.from_create_model(role)
            session.add(role_schema)
            session.commit()
            return role_schema.to_model()

    def _get_role(self, role_name_or_id: UUID) -> RoleModel:
        """Gets a specific role.

        Args:
            role_name_or_id: Name or ID of the role to get.

        Returns:
            The requested role.

        Raises:
            KeyError: If no role with the given name exists.
        """
        role = self._get_schema_by_name_or_id(
            object_name_or_id=role_name_or_id,
            schema_class=RoleSchema,
            schema_name="role",
        )
        return role.to_model()

    def _delete_role(self, role_id: UUID) -> None:
        """Deletes a role.

        Args:
            role_id: ID of the role to delete.

        Raises:
            KeyError: If no role with the given ID exists.
        """
        with Session(self.engine) as session:
            # Check if role with the given ID exists
            role = session.exec(
                select(RoleSchema).where(RoleSchema.id == role_id)
            ).first()
            if role is None:
                raise KeyError(
                    f"Unable to delete role with id '{role_id}': No role found "
                    "with this id."
                )

            # Delete role
            session.delete(role)
            session.commit()

    def list_role_assignments(
        self,
        project_name_or_id: Optional[Union[str, UUID]] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[RoleAssignmentModel]:
        """List all role assignments.

        Args:
            project_name_or_id: Name or Id of the Project for the role
                                assignment
            team_id: If provided, only list assignments for the given team
            user_id: If provided, only list assignments for the given user

        Returns:
            A list of all role assignments.
        """
        with Session(self.engine) as session:
            # Get user role assignments
            query = select(UserRoleAssignmentSchema)

            if project_name_or_id is not None:
                project = self._get_project_schema(project_name_or_id)
                query = query.where(
                    UserRoleAssignmentSchema.project_id == project.id
                )
            if user_id is not None:
                query = query.where(UserRoleAssignmentSchema.user_id == user_id)
            user_role_assignments = session.exec(query).all()

            # Get team role assignments
            query = select(TeamRoleAssignmentSchema)
            if project_name_or_id is not None:
                project = self._get_project_schema(project_name_or_id)
                query = query.where(
                    TeamRoleAssignmentSchema.project_id == project.id
                )
            if team_id is not None:
                query = query.where(TeamRoleAssignmentSchema.team_id == team_id)
            team_role_assignments = session.exec(query).all()

        return [
            role_assignment.to_model()
            for role_assignment in user_role_assignments + team_role_assignments
        ]

    def _assign_role(
        self,
        project_name_or_id: Optional[Union[str, UUID]],
        role_id: UUID,
        user_or_team_id: UUID,
        is_user: bool = True,
    ) -> None:
        """Assigns a role to a user or team, scoped to a specific project.

        Args:
            project_name_or_id: Optional ID of a project in which to assign the role.
                If this is not provided, the role will be assigned globally.
            role_id: ID of the role to assign.
            user_or_team_id: ID of the user or team to which to assign the role.
            is_user: Whether `user_or_team_id` refers to a user or a team.

        Raises:
            EntityExistsError: If the role assignment already exists.
        """
        # TODO: Check if the role assignment already exists + raise error
        with Session(self.engine) as session:
            # Check if role with the given name already exists
            role = session.exec(
                select(RoleSchema).where(RoleSchema.id == role_id)
            ).first()
            if role is None:
                raise KeyError(
                    f"Unable to assign role with id '{role_id}': "
                    "No role with this id found."
                )

            project = self._get_project_schema(project_name_or_id)

            # Assign role to user
            if is_user:
                user = session.exec(
                    select(UserSchema).where(UserSchema.id == user_or_team_id)
                ).first()
                if user is None:
                    raise KeyError(
                        "Unable to assign role to user with id "
                        f"'{user_or_team_id}': No user with this id found."
                    )
                role_assignment = UserRoleAssignmentSchema(
                    role_id=role_id,
                    user_id=user_or_team_id,
                    project_id=project.id,
                    role=role,
                    user=user,
                    project=project,
                )

            # Assign role to team
            else:
                team = session.exec(
                    select(TeamSchema).where(TeamSchema.id == user_or_team_id)
                ).first()
                if team is None:
                    raise KeyError(
                        "Unable to assign role to team with id "
                        f"'{user_or_team_id}': No team with this id found."
                    )
                role_assignment = TeamRoleAssignmentSchema(
                    role_id=role_id,
                    team_id=user_or_team_id,
                    project_id=project.id,
                    role=role,
                    team=team,
                    project=project,
                )

            session.add(role_assignment)
            session.commit()

    def _revoke_role(
        self,
        project_name_or_id: Optional[Union[str, UUID]],
        role_id: UUID,
        user_or_team_id: UUID,
        is_user: bool = True,
    ) -> None:
        """Revokes a role from a user or team for a given project.

        Args:
            project_name_or_id: Optional ID of a project in which to revoke the role.
                If this is not provided, the role will be revoked globally.
            role_id: ID of the role to revoke.
            user_or_team_id: ID of the user or team from which to revoke the
                role.
            is_user: Whether `user_or_team_id` refers to a user or a team.

        Raises:
            KeyError: If the role, user, team, or project does not exists.
        """
        with Session(self.engine) as session:
            project = self._get_project_schema(project_name_or_id)
            if is_user:
                role = session.exec(
                    select(UserRoleAssignmentSchema)
                    .where(UserRoleAssignmentSchema.user_id == user_or_team_id)
                    .where(UserRoleAssignmentSchema.role_id == role_id)
                    .where(UserRoleAssignmentSchema.project_id == project.id)
                ).first()
            else:
                role = session.exec(
                    select(TeamRoleAssignmentSchema)
                    .where(TeamRoleAssignmentSchema.team_id == user_or_team_id)
                    .where(TeamRoleAssignmentSchema.role_id == role_id)
                    .where(TeamRoleAssignmentSchema.project_id == project.id)
                ).first()

            if role is None:
                assignee = "user" if is_user else "team"
                scope = f" in project {project.name}" if project.id else ""
                raise KeyError(
                    f"Unable to unassign role {role_id} from {assignee} "
                    f"{user_or_team_id}{scope}: The role is currently not "
                    f"assigned to the {assignee}."
                )

            session.delete(role)
            session.commit()

    #  .---------.
    # | PROJECTS |
    # '----------'

    def _list_projects(self) -> List[ProjectModel]:
        """List all projects.

        Returns:
            A list of all projects.
        """
        with Session(self.engine) as session:
            projects = session.exec(select(ProjectSchema)).all()
            return [project.to_model() for project in projects]

    def _create_project(self, project: ProjectModel) -> ProjectModel:
        """Creates a new project.

        Args:
            project: The project to create.

        Returns:
            The newly created project.

        Raises:
            EntityExistsError: If a project with the given name already exists.
        """
        with Session(self.engine) as session:
            # Check if project with the given name already exists
            existing_project = session.exec(
                select(ProjectSchema).where(ProjectSchema.name == project.name)
            ).first()
            if existing_project is not None:
                raise EntityExistsError(
                    f"Unable to create project {project.name}: "
                    "A project with this name already exists."
                )

            # Create the project
            new_project = ProjectSchema.from_create_model(project)
            session.add(new_project)
            session.commit()

            # After committing the model, sqlmodel takes care of updating the
            # object with id, created_at, etc ...

            return new_project.to_model()

    def _get_project(self, project_name_or_id: UUID) -> ProjectModel:
        """Get an existing project by name or ID.

        Args:
            project_name_or_id: Name or ID of the project to get.

        Returns:
            The requested project if one was found.

        Raises:
            KeyError: If there is no such project.
        """
        project = self._get_project_schema(project_name_or_id)
        return project.to_model()

    def _update_project(
        self, project_name: str, project: ProjectModel
    ) -> ProjectModel:
        """Update an existing project.

        Args:
            project_name: Name of the project to update.
            project: The project to use for the update.

        Returns:
            The updated project.

        Raises:
            KeyError: if the project does not exist.
        """
        with Session(self.engine) as session:
            # Check if project with the given name already exists
            existing_project = session.exec(
                select(ProjectSchema).where(ProjectSchema.name == project_name)
            ).first()
            if existing_project is None:
                raise KeyError(
                    f"Unable to update project {project_name}: "
                    "No project with this name found."
                )

            # Update the project
            existing_project.from_update_model(project)
            # other fields are not updatable
            session.add(existing_project)
            session.commit()

            return existing_project.to_model()

    def _delete_project(self, project_name: str) -> None:
        """Deletes a project.

        Args:
            project_name: Name of the project to delete.

        Raises:
            KeyError: If no project with the given name exists.
        """
        with Session(self.engine) as session:
            # Check if project with the given name exists
            project = session.exec(
                select(ProjectSchema).where(ProjectSchema.name == project_name)
            ).first()
            if project is None:
                raise KeyError(
                    f"Unable to delete project {project_name}: "
                    "No project with this name found."
                )

            session.delete(project)  # TODO: cascade delete
            session.commit()

    def _get_default_stack(self, project_name: str) -> StackModel:
        """Gets the default stack in a project.

        Args:
            project_name: Name of the project to get.

        Returns:
            The default stack in the project.

        Raises:
            KeyError: if the project doesn't exist.
        """
        pass  # TODO

    def _set_default_stack(
        self, project_name: str, stack_id: UUID
    ) -> StackModel:
        """Sets the default stack in a project.

        Args:
            project_name: Name of the project to set.
            stack_id: The ID of the stack to set as the default.

        Raises:
            KeyError: if the project or stack doesn't exist.
        """
        pass  # TODO

    #  .-------------.
    # | REPOSITORIES |
    # '--------------'

    # TODO: create repos?

    def _list_project_repositories(
        self, project_name: str
    ) -> List[CodeRepositoryModel]:
        """Get all repositories in the project.

        Args:
            project_name: The name of the project.

        Returns:
            A list of all repositories in the project.

        Raises:
            KeyError: if the project doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if project with the given name already exists
            project = session.exec(
                select(ProjectSchema).where(ProjectSchema.name == project_name)
            ).first()
            if project is None:
                raise KeyError(
                    f"Unable to list repositories in project {project_name}: "
                    "No project with this name found."
                )

            # Get all repositories in the project
            repositories = session.exec(
                select(CodeRepositorySchema).where(
                    CodeRepositorySchema.project_id == project.id
                )
            ).all()

        return [repository.to_model() for repository in repositories]

    def _connect_project_repository(
        self, project_name: str, repository: CodeRepositoryModel
    ) -> CodeRepositoryModel:
        """Connects a repository to a project.

        Args:
            project_name: Name of the project to connect the repository to.
            repository: The repository to connect.

        Returns:
            The connected repository.

        Raises:
            KeyError: if the project or repository doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if project with the given name already exists
            project = session.exec(
                select(ProjectSchema).where(ProjectSchema.name == project_name)
            ).first()
            if project is None:
                raise KeyError(
                    f"Unable to connect repository with ID {repository.id} to "
                    f"project {project_name}: No project with this name found."
                )

            # Check if repository with the given name already exists
            existing_repository = session.exec(
                select(CodeRepositorySchema).where(
                    CodeRepositorySchema.id == repository.id
                )
            ).first()
            if existing_repository is None:
                raise KeyError(
                    f"Unable to connect repository with ID {repository.id} to "
                    f"project {project_name}: No repository with this ID found."
                )

            # Connect the repository to the project
            existing_repository.project_id = project.id
            session.add(existing_repository)
            session.commit()

            return existing_repository.to_model()

    def _get_repository(self, repository_id: UUID) -> CodeRepositoryModel:
        """Get a repository by ID.

        Args:
            repository_id: The ID of the repository to get.

        Returns:
            The repository.

        Raises:
            KeyError: if the repository doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if repository with the given ID exists
            existing_repository = session.exec(
                select(CodeRepositorySchema).where(
                    CodeRepositorySchema.id == repository_id
                )
            ).first()
            if existing_repository is None:
                raise KeyError(
                    f"Unable to get repository with ID {repository_id}: "
                    "No repository with this ID found."
                )

            return existing_repository.to_model()

    def _update_repository(
        self, repository_id: UUID, repository: CodeRepositoryModel
    ) -> CodeRepositoryModel:
        """Update a repository.

        Args:
            repository_id: The ID of the repository to update.
            repository: The repository to use for the update.

        Returns:
            The updated repository.

        Raises:
            KeyError: if the repository doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if repository with the given ID exists
            existing_repository = session.exec(
                select(CodeRepositorySchema).where(
                    CodeRepositorySchema.id == repository_id
                )
            ).first()
            if existing_repository is None:
                raise KeyError(
                    f"Unable to update repository with ID {repository_id}: "
                    "No repository with this ID found."
                )

            # Update the repository
            existing_repository.from_update_model(repository)
            session.add(existing_repository)
            session.commit()

            return existing_repository.to_model()

    def _delete_repository(self, repository_id: UUID) -> None:
        """Delete a repository.

        Args:
            repository_id: The ID of the repository to delete.

        Raises:
            KeyError: if the repository doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if repository with the given ID exists
            existing_repository = session.exec(
                select(CodeRepositorySchema).where(
                    CodeRepositorySchema.id == repository_id
                )
            ).first()
            if existing_repository is None:
                raise KeyError(
                    f"Unable to delete repository with ID {repository_id}: "
                    "No repository with this ID found."
                )

            session.delete(existing_repository)  # TODO: handle dependencies
            session.commit()

    #  .----------.
    # | PIPELINES |
    # '-----------'

    def _list_pipelines(
        self,
        project_name_or_id: Optional[Union[str, UUID]] = None,
    ) -> List[PipelineModel]:
        """List all pipelines in the project.

        Args:
            project_name_or_id: If provided, only list pipelines in this
                project.

        Returns:
            A list of pipelines.

        Raises:
            KeyError: if the project does not exist.
        """
        with Session(self.engine) as session:
            # Check if project with the given name exists
            query = select(PipelineSchema)
            if project_name_or_id is not None:
                project = self._get_project_schema(project_name_or_id)
                query = query.where(PipelineSchema.project_id == project.id)

            # Get all pipelines in the project
            pipelines = session.exec(query).all()
            return [pipeline.to_model() for pipeline in pipelines]

    def _create_pipeline(
        self, project_name_or_id: Union[str, UUID], pipeline: PipelineModel
    ) -> PipelineModel:
        """Creates a new pipeline in a project.

        Args:
            project_name_or_id: ID or name of the project to create the pipeline
                in.
            pipeline: The pipeline to create.

        Returns:
            The newly created pipeline.

        Raises:
            KeyError: if the project does not exist.
            EntityExistsError: If an identical pipeline already exists.
        """
        with Session(self.engine) as session:
            # Check if project with the given name exists
            project = self._get_project_schema(project_name_or_id)

            # Check if pipeline with the given name already exists
            existing_pipeline = session.exec(
                select(PipelineSchema)
                .where(PipelineSchema.name == pipeline.name)
                .where(PipelineSchema.project_id == project.id)
            ).first()
            if existing_pipeline is not None:
                raise EntityExistsError(
                    f"Unable to create pipeline in project {project_name_or_id}: "
                    f"A pipeline with this name already exists."
                )

            # Create the pipeline
            new_pipeline = PipelineSchema.from_create_model(pipeline)
            session.add(new_pipeline)
            session.commit()

            # After committing the model, sqlmodel takes care of updating the
            # object with id, created_at, etc ...

            return new_pipeline.to_model()

    def get_pipeline(self, pipeline_id: UUID) -> Optional[PipelineModel]:
        """Get a pipeline with a given ID.

        Args:
            pipeline_id: ID of the pipeline.

        Returns:
            The pipeline.

        Raises:
            KeyError: if the pipeline does not exist.
        """
        with Session(self.engine) as session:
            # Check if pipeline with the given ID exists
            pipeline = session.exec(
                select(PipelineSchema).where(PipelineSchema.id == pipeline_id)
            ).first()
            if pipeline is None:
                raise KeyError(
                    f"Unable to get pipeline with ID '{pipeline_id}': "
                    "No pipeline with this ID found."
                )

            return pipeline.to_model()

    def get_pipeline_in_project(
        self,
        pipeline_name: str,
        project_name_or_id: Union[str, UUID],
    ) -> Optional[PipelineModel]:
        """Get a pipeline with a given name in a project.

        Args:
            pipeline_name: Name of the pipeline.
            project_name_or_id: ID or name of the project.

        Returns:
            The pipeline.

        Raises:
            KeyError: if the pipeline does not exist.
        """
        with Session(self.engine) as session:
            project = self._get_project_schema(project_name_or_id)
            # Check if pipeline with the given name exists in the project
            pipeline = session.exec(
                select(PipelineSchema).where(
                    PipelineSchema.name == pipeline_name,
                    PipelineSchema.project_id == project.id,
                )
            ).first()
            if pipeline is None:
                raise KeyError(
                    f"Unable to get pipeline '{pipeline_name}' in project "
                    f"'{project_name_or_id}': No pipeline with this name found."
                )
            return pipeline.to_model()

    def _update_pipeline(
        self, pipeline_id: UUID, pipeline: PipelineModel
    ) -> PipelineModel:
        """Updates a pipeline.

        Args:
            pipeline_id: The ID of the pipeline to update.
            pipeline: The pipeline to use for the update.

        Returns:
            The updated pipeline.

        Raises:
            KeyError: if the pipeline doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if pipeline with the given ID exists
            existing_pipeline = session.exec(
                select(PipelineSchema).where(PipelineSchema.id == pipeline_id)
            ).first()
            if existing_pipeline is None:
                raise KeyError(
                    f"Unable to update pipeline with ID {pipeline_id}: "
                    f"No pipeline with this ID found."
                )

            # Update the pipeline
            existing_pipeline.from_update_model(pipeline)

            session.add(existing_pipeline)
            session.commit()

            return existing_pipeline.to_model()

    def _delete_pipeline(self, pipeline_id: UUID) -> None:
        """Deletes a pipeline.

        Args:
            pipeline_id: The ID of the pipeline to delete.

        Raises:
            KeyError: if the pipeline doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if pipeline with the given ID exists
            pipeline = session.exec(
                select(PipelineSchema).where(PipelineSchema.id == pipeline_id)
            ).first()
            if pipeline is None:
                raise KeyError(
                    f"Unable to delete pipeline with ID {pipeline_id}: "
                    f"No pipeline with this ID found."
                )

            session.delete(pipeline)
            session.commit()

    def _get_pipeline_configuration(self, pipeline_id: UUID) -> Dict[str, str]:
        """Gets the pipeline configuration.

        Args:
            pipeline_id: The ID of the pipeline to get.

        Returns:
            The pipeline configuration.

        Raises:
            KeyError: if the pipeline doesn't exist.
        """
        return self.get_pipeline(pipeline_id).configuration

    def _list_steps(self, pipeline_id: UUID) -> List[StepRunModel]:
        """List all steps.

        Args:
            pipeline_id: The ID of the pipeline to list steps for.

        Returns:
            A list of all steps.
        """
        pass  # TODO

    #  .-----.
    # | RUNS |
    # '------'

    def _sync_runs(self):
        """Sync runs from the database with those registered in MLMD."""
        with Session(self.engine) as session:
            zenml_runs = session.exec(select(PipelineRunSchema)).all()
        zenml_runs = {run.name: run.to_model() for run in zenml_runs}
        mlmd_runs = self.metadata_store.get_all_runs()
        for run_name, mlmd_id in mlmd_runs.items():

            # If the run is in MLMD but not in ZenML, we create it
            if run_name not in zenml_runs:
                new_run = PipelineRunModel(name=run_name, mlmd_id=mlmd_id)
                self._create_run(new_run)
                continue

            # If an existing run had no MLMD ID, we update it
            existing_run = zenml_runs[run_name]
            if not existing_run.mlmd_id:
                existing_run.mlmd_id = mlmd_id
                self._update_run(run_id=existing_run.id, run=existing_run)

    def _list_runs(
        self,
        project_name_or_id: Optional[Union[str, UUID]] = None,
        stack_id: Optional[str] = None,
        user_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        unlisted: bool = False,
    ) -> List[PipelineRunModel]:
        """Gets all pipeline runs.

        Args:
            project_name_or_id: If provided, only return runs for this project.
            stack_id: If provided, only return runs for this stack.
            user_id: If provided, only return runs for this user.
            pipeline_id: If provided, only return runs for this pipeline.
            unlisted: If True, only return unlisted runs that are not
                associated with any pipeline (filter by pipeline_id==None).

        Returns:
            A list of all pipeline runs.
        """
        # TODO: [server] this filters the list by on of the filter parameters,
        #  not all, this might have to be redone
        self._sync_runs()  # Sync with MLMD
        with Session(self.engine) as session:
            query = select(PipelineRunSchema).where(
                PipelineRunSchema.stack_id == StackSchema.id
            )
            if project_name_or_id is not None:
                project = self._get_project_schema(project_name_or_id)
                query = query.where(StackSchema.project_id == project.id)
            if stack_id is not None:
                query = query.where(PipelineRunSchema.stack_id == stack_id)
            if pipeline_id is not None:
                query = query.where(
                    PipelineRunSchema.pipeline_id == pipeline_id
                )
            elif unlisted:
                query = query.where(PipelineRunSchema.pipeline_id == None)
            if user_id is not None:
                query = query.where(PipelineRunSchema.owner == user_id)
            runs = session.exec(query).all()
            return [run.to_model() for run in runs]

    def _create_run(self, pipeline_run: PipelineRunModel) -> PipelineRunModel:
        """Creates a pipeline run.

        Args:
            pipeline_run: The pipeline run to create.

        Returns:
            The created pipeline run.

        Raises:
            EntityExistsError: If an identical pipeline run already exists.
        """
        with Session(self.engine) as session:
            # Check if pipeline run already exists
            existing_run = session.exec(
                select(PipelineRunSchema).where(
                    PipelineRunSchema.name == pipeline_run.name
                )
            ).first()
            if existing_run is not None:
                raise EntityExistsError(
                    f"Unable to create pipeline run {pipeline_run.name}: "
                    f"A pipeline run with this name already exists."
                )

            # Query pipeline
            if pipeline_run.pipeline_id is not None:
                pipeline = session.exec(
                    select(PipelineSchema).where(
                        PipelineSchema.id == pipeline_run.pipeline_id
                    )
                ).first()
                if pipeline is None:
                    raise KeyError(
                        f"Unable to create pipeline run: {pipeline_run.name}: "
                        f"No pipeline with ID {pipeline_run.pipeline_id} found."
                    )
                new_run = PipelineRunSchema.from_create_model(
                    model=pipeline_run, pipeline=pipeline
                )
            else:
                new_run = PipelineRunSchema.from_create_model(pipeline_run)

            # Create the pipeline run
            session.add(new_run)
            session.commit()

            # After committing the model, sqlmodel takes care of updating the
            # object with id, created_at, etc ...

            return new_run.to_model()

    def _get_run(self, run_id: UUID) -> PipelineRunModel:
        """Gets a pipeline run.

        Args:
            run_id: The ID of the pipeline run to get.

        Returns:
            The pipeline run.

        Raises:
            KeyError: if the pipeline run doesn't exist.
        """
        self._sync_runs()  # Sync with MLMD
        with Session(self.engine) as session:
            # Check if pipeline run with the given ID exists
            run = session.exec(
                select(PipelineRunSchema).where(PipelineRunSchema.id == run_id)
            ).first()
            if run is None:
                raise KeyError(
                    f"Unable to get pipeline run with ID {run_id}: "
                    f"No pipeline run with this ID found."
                )

            return run.to_model()

    def get_run_in_project(
        self,
        run_name: str,
        project_name_or_id: Union[str, UUID],
    ) -> Optional[PipelineRunModel]:
        """Get a pipeline run with a given name in a project.

        Args:
            run_name: Name of the pipeline run.
            project_name_or_id: ID of the project.

        Returns:
            The pipeline run.

        Raises:
            KeyError: if the pipeline run doesn't exist.
        """
        self._sync_runs()  # Sync with MLMD
        with Session(self.engine) as session:
            project = self._get_project_schema(project_name_or_id)
            # Check if pipeline run with the given name exists in the project
            run = session.exec(
                select(PipelineRunSchema)
                .where(PipelineRunSchema.name == run_name)
                .where(PipelineRunSchema.stack_id == StackSchema.id)
                .where(StackSchema.project_id == project.id)
            ).first()
            if run is None:
                raise KeyError(
                    f"Unable to get pipeline run '{run_name}' in project "
                    f"'{project_name_or_id}': No pipeline run with this name "
                    "found."
                )

            return run.to_model()

    def _update_run(
        self, run_id: UUID, run: PipelineRunModel
    ) -> PipelineRunModel:
        """Updates a pipeline run.

        Args:
            run_id: The ID of the pipeline run to update.
            run: The pipeline run to use for the update.

        Returns:
            The updated pipeline run.

        Raises:
            KeyError: if the pipeline run doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if pipeline run with the given ID exists
            existing_run = session.exec(
                select(PipelineRunSchema).where(PipelineRunSchema.id == run_id)
            ).first()
            if existing_run is None:
                raise KeyError(
                    f"Unable to update pipeline run with ID {run_id}: "
                    f"No pipeline run with this ID found."
                )

            # Update the pipeline run
            existing_run.from_update_model(run)

            session.add(existing_run)
            session.commit()

            return existing_run.to_model()

    def _delete_run(self, run_id: UUID) -> None:
        """Deletes a pipeline run.

        Args:
            run_id: The ID of the pipeline run to delete.

        Raises:
            KeyError: if the pipeline run doesn't exist.
        """
        with Session(self.engine) as session:
            # Check if pipeline run with the given ID exists
            run = session.exec(
                select(PipelineRunSchema).where(PipelineRunSchema.id == run_id)
            ).first()
            if run is None:
                raise KeyError(
                    f"Unable to delete pipeline run with ID {run_id}: "
                    f"No pipeline run with this ID found."
                )

            # Delete the pipeline run
            session.delete(run)  # TODO: this doesn't delete from MLMD
            session.commit()

    def _get_run_dag(self, run_id: UUID) -> str:
        """Gets the DAG for a pipeline run.

        Args:
            run_id: The ID of the pipeline run to get.

        Returns:
            The DAG for the pipeline run.

        Raises:
            KeyError: if the pipeline run doesn't exist.
        """
        pass  # TODO

    def _get_run_runtime_configuration(self, run_id: UUID) -> Dict:
        """Gets the runtime configuration for a pipeline run.

        Args:
            run_id: The ID of the pipeline run to get.

        Returns:
            The runtime configuration for the pipeline run.

        Raises:
            KeyError: if the pipeline run doesn't exist.
        """
        run = self._get_run(run_id)
        return run.runtime_configuration

    def _get_run_component_side_effects(
        self,
        run_id: UUID,
        component_id: Optional[str] = None,
        component_type: Optional[StackComponentType] = None,
    ) -> Dict:
        """Gets the side effects for a component in a pipeline run.

        Args:
            run_id: The ID of the pipeline run to get.
            component_id: The ID of the component to get.

        Returns:
            The side effects for the component in the pipeline run.

        Raises:
            KeyError: if the pipeline run doesn't exist.
        """
        pass  # TODO

    #  .------.
    # | STEPS |
    # '-------'

    def list_run_steps(self, run_id: int) -> List[StepRunModel]:
        """Gets all steps in a pipeline run.

        Args:
            run_id: The ID of the pipeline run for which to list runs.

        Returns:
            A list of all steps in the pipeline run.
        """
        return self.metadata_store.get_pipeline_run_steps(run_id)

    def get_run_step(self, step_id: int) -> StepRunModel:
        """Get a step by ID.

        Args:
            step_id: The ID of the step to get.

        Returns:
            The step.

        Raises:
            KeyError: if the step doesn't exist.
        """
        return self.metadata_store.get_step_by_id(step_id)

    def get_run_step_artifacts(
        self, step: StepRunModel
    ) -> Tuple[Dict[str, ArtifactModel], Dict[str, ArtifactModel]]:
        """Returns input and output artifacts for the given step.

        Args:
            step: The step for which to get the artifacts.

        Returns:
            A tuple (inputs, outputs) where inputs and outputs
            are both Dicts mapping artifact names
            to the input and output artifacts respectively.
        """
        return self.metadata_store.get_step_artifacts(step)

    def get_run_step_status(self, step_id: int) -> ExecutionStatus:
        """Gets the execution status of a single step.

        Args:
            step_id: The ID of the step to get the status for.

        Returns:
            ExecutionStatus: The status of the step.
        """
        return self.metadata_store.get_step_status(step_id=step_id)

    # .----------.
    # | METADATA |
    # '----------'

    def get_metadata_config(self) -> str:
        """Get the TFX metadata config of this ZenStore.

        Returns:
            The TFX metadata config of this ZenStore.
        """
        from google.protobuf.json_format import MessageToJson

        config = self.metadata_store.get_tfx_metadata_config()
        return MessageToJson(config)

    # .-------------------------.
    # | INTERNAL HELPER METHODS |
    # '-------------------------'

    def _get_schema_by_name_or_id(
        self,
        object_name_or_id: Union[str, UUID],
        schema_class: Type[SQLModel],
        schema_name: str,
    ) -> SQLModel:
        """Query a schema by its 'name' or 'id' field.

        Args:
            object_name_or_id: The name or ID of the object to query.
            schema_class: The schema class to query. E.g., `ProjectSchema`.
            schema_name: The name of the schema used for error messages.
                E.g., "project".

        Returns:
            The schema object.

        Raises:
            KeyError: if the object couldn't be found.
        """
        if uuid_utils.is_valid_uuid(object_name_or_id):
            filter = schema_class.id == object_name_or_id
            error_msg = (
                f"Unable to get {schema_name} with name or ID "
                f"'{object_name_or_id}': No {schema_name} with this ID found."
            )
        else:
            filter = schema_class.name == object_name_or_id
            error_msg = (
                f"Unable to get {schema_name} with name or ID "
                f"'{object_name_or_id}': '{object_name_or_id}' is not a valid "
                f" UUID and no {schema_name} with this name exists."
            )
        with Session(self.engine) as session:
            schema = session.exec(select(schema_class).where(filter)).first()
            if schema is None:
                raise KeyError(error_msg)
            return schema

    def _get_project_schema(
        self, project_name_or_id: Union[str, UUID]
    ) -> ProjectSchema:
        """Gets a project schema by name or ID.

        This is a helper method that is used in various places to find the
        project associated to some other object.

        Args:
            project_name_or_id: The name or ID of the project to get.

        Returns:
            The project schema.

        Raises:
            KeyError: if the project doesn't exist.
        """
        return self._get_schema_by_name_or_id(
            object_name_or_id=project_name_or_id,
            schema_class=ProjectSchema,
            schema_name="project",
        )

    # LEGACY CODE FROM THE PREVIOUS VERSION OF BASEZENSTORE

    # Handling stack component flavors

    @property
    def flavors(self) -> List[FlavorModel]:
        """All registered flavors.

        Returns:
            A list of all registered flavors.
        """
        with Session(self.engine) as session:
            return [
                FlavorModel(**flavor.dict())
                for flavor in session.exec(select(FlavorSchema)).all()
            ]

    def _create_flavor(
        self,
        source: str,
        name: str,
        stack_component_type: StackComponentType,
    ) -> FlavorModel:
        """Creates a new flavor.

        Args:
            source: the source path to the implemented flavor.
            name: the name of the flavor.
            stack_component_type: the corresponding StackComponentType.

        Returns:
            The newly created flavor.

        Raises:
            EntityExistsError: If a flavor with the given name and type
                already exists.
        """
        with Session(self.engine) as session:
            existing_flavor = session.exec(
                select(FlavorSchema).where(
                    FlavorSchema.name == name,
                    FlavorSchema.type == stack_component_type,
                )
            ).first()
            if existing_flavor:
                raise EntityExistsError(
                    f"A {stack_component_type} with '{name}' flavor already "
                    f"exists."
                )
            sql_flavor = FlavorSchema(
                name=name,
                source=source,
                type=stack_component_type,
            )
            flavor_wrapper = FlavorModel(**sql_flavor.dict())
            session.add(sql_flavor)
            session.commit()
        return flavor_wrapper

    def get_flavors_by_type(
        self, component_type: StackComponentType
    ) -> List[FlavorModel]:
        """Fetch all flavor defined for a specific stack component type.

        Args:
            component_type: The type of the stack component.

        Returns:
            List of all the flavors for the given stack component type.
        """
        # TODO: [ALEXEJ] This should be list_flavors with a filter
        with Session(self.engine) as session:
            flavors = session.exec(
                select(FlavorSchema).where(FlavorSchema.type == component_type)
            ).all()
        return [
            FlavorModel(
                name=f.name,
                source=f.source,
                type=f.type,
                integration=f.integration,
            )
            for f in flavors
        ]

    def get_flavor_by_name_and_type(
        self,
        flavor_name: str,
        component_type: StackComponentType,
    ) -> FlavorModel:
        """Fetch a flavor by a given name and type.

        Args:
            flavor_name: The name of the flavor.
            component_type: Optional, the type of the component.

        Returns:
            Flavor instance if it exists

        Raises:
            KeyError: If no flavor exists with the given name and type
                or there are more than one instances
        """
        with Session(self.engine) as session:
            try:
                flavor = session.exec(
                    select(FlavorSchema).where(
                        FlavorSchema.name == flavor_name,
                        FlavorSchema.type == component_type,
                    )
                ).one()
                return FlavorModel(
                    name=flavor.name,
                    source=flavor.source,
                    type=flavor.type,
                    integration=flavor.integration,
                )
            except NoResultFound as error:
                raise KeyError from error

    # TODO: [ALEXEJ] This should be list_flavors with a filter
