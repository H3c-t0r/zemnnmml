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
"""REST API user management models implementation."""


from typing import Optional

from pydantic import BaseModel, SecretStr

from zenml.models.user_management_models import UserModel


class CreateUserModel(BaseModel):
    """Model used for all create operations on users.

    Attributes:
        name: Name of the user.
        full_name: Full name for the user account.
        email: Email address for the user account.
        password: Password for the user account.
    """

    name: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[SecretStr] = None

    def to_model(self) -> UserModel:
        """Create a `UserModel` from this object.

        Returns:
            The created `UserModel`.
        """
        return UserModel(
            **self.dict(exclude_none=True),
        )


class CreateUserResponse(UserModel):
    """Pydantic object representing a user create response.

    The activation token is included in the response.
    """

    activation_token: Optional[str] = None

    @classmethod
    def from_model(cls, user: UserModel) -> "CreateUserResponse":
        """Create a `CreateUserResponse` from a `UserModel`.

        Args:
            user: The `UserModel` to create the response from.

        Returns:
            The created `CreateUserResponse`.
        """
        response = cls(
            **user.dict(), activation_token=user.get_activation_token()
        )
        return response


class UpdateUserRequest(BaseModel):
    """Model used for all update operations on users.

    Attributes:
        name: Name of the user.
        full_name: Full name for the user account.
        email: Email address for the user account.
        password: Password for the user account.
    """

    name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[SecretStr] = None

    def to_model(self, user: UserModel) -> UserModel:
        """Update a `UserModel` from this object.

        Args:
            user: The `UserModel` to apply the changes to.

        Returns:
            The updated `UserModel`.
        """
        for k, v in self.dict(exclude_none=True).items():
            setattr(user, k, v)
        if self.password is not None:
            user.password = self.password.get_secret_value()
        return user


class ActivateUserRequest(BaseModel):
    """Pydantic object representing a user activation request.

    Attributes:
        name: Name of the user.
        full_name: Full name for the user account.
        email: Email address for the user account.
        password: Password for the user account.
        activation_token: Activation token for the user account.
    """

    name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: SecretStr
    activation_token: SecretStr

    def to_model(self, user: UserModel) -> UserModel:
        """Apply the changes to a `UserModel`.

        Args:
            user: The `UserModel` to apply the changes to.

        Returns:
            The updated `UserModel`.
        """
        for k, v in self.dict(exclude_none=True).items():
            if k in ["activation_token", "password"]:
                continue
            setattr(user, k, v)
        user.password = self.password.get_secret_value()
        return user


class DeactivateUserResponse(UserModel):
    """Pydantic object representing a user deactivation response.

    Attributes:
        activation_token: Activation token for the user account.
    """

    activation_token: str

    @classmethod
    def from_model(cls, user: UserModel) -> "DeactivateUserResponse":
        """Create a `DeactivateUserResponse` from a `UserModel`.

        Args:
            user: The `UserModel` to create the response from.

        Returns:
            The created `DeactivateUserResponse`.
        """
        response = cls(
            **user.dict(), activation_token=user.get_activation_token()
        )
        return response
