#  Copyright (c) ZenML GmbH 2024. All Rights Reserved.
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
"""Implementation of the github webhook event source."""
import hashlib
import hmac
import json
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional, Type
from uuid import UUID

from pydantic import BaseModel, Extra

from zenml import EventSourceRequest, SecretRequest
from zenml.event_sources.base_event_source_plugin import BaseEvent
from zenml.event_sources.webhooks.base_webhook_event_plugin import (
    BaseWebhookEventSourcePlugin,
    WebhookEventFilterConfig,
    WebhookEventSourceConfig,
)
from zenml.logger import get_logger
from zenml.models import (
    EventSourceResponse,
    TriggerFilter,
    TriggerResponse,
)
from zenml.utils.enum_utils import StrEnum
from zenml.utils.pagination_utils import depaginate
from zenml.utils.secret_utils import SecretField
from zenml.utils.string_utils import random_str

logger = get_logger(__name__)

# -------------------- Utils -----------------------------------


class GithubEventType(StrEnum):
    """Collection of all possible Github Events."""

    PUSH_EVENT = "push_event"
    TAG_EVENT = "tag_event"
    PR_EVENT = "pull_request_event"


# -------------------- Github Event Models -----------------------------------


class User(BaseModel):
    """Github User."""

    name: str
    email: str
    username: str


class Commit(BaseModel):
    """Github Event."""

    id: str
    message: str
    url: str
    author: User


class Tag(BaseModel):
    """Github Tag."""

    id: str
    name: str
    commit: Commit


class PullRequest(BaseModel):
    """Github Pull Request."""

    id: str
    number: int
    title: str
    author: User
    merged: bool
    merge_commit: Commit


class Repository(BaseModel):
    """Github Repository."""

    id: int
    name: str
    full_name: str
    html_url: str


class GithubEvent(BaseEvent):
    """Push Event from Github."""

    ref: str
    before: str
    after: str
    repository: Repository
    commits: List[Commit]
    head_commit: Optional[Commit]
    tags: Optional[List[Tag]]
    pull_requests: Optional[List[PullRequest]]

    class Config:
        """Pydantic configuration class."""

        extra = Extra.allow

    @property
    def branch(self) -> Optional[str]:
        """THe branch the event happened on."""
        if self.ref.startswith("refs/heads/"):
            return "/".join(self.ref.split("/")[2:])
        return None

    @property
    def event_type(self) -> str:
        """The type of github event."""
        if self.ref.startswith("refs/heads/"):
            return GithubEventType.PUSH_EVENT
        elif self.ref.startswith("refs/tags/"):
            return GithubEventType.TAG_EVENT
        elif len(self.pull_requests) > 0:
            return GithubEventType.PR_EVENT
        else:
            return "unknown"


# -------------------- Configuration Models ----------------------------------


class GithubWebhookEventFilterConfiguration(WebhookEventFilterConfig):
    """Configuration for github event filters."""

    repo: Optional[str]
    branch: Optional[str]
    event_type: Optional[GithubEventType]

    def event_matches_filter(self, event: GithubEvent) -> bool:
        """Checks the filter against the inbound event."""
        if self.event_type and event.event_type != self.event_type:
            # Mismatch for the action
            return False
        if self.repo and event.repository.full_name != self.repo:
            # Mismatch for the repository
            return False
        if self.branch and event.branch != self.branch:
            # Mismatch for the branch
            return False
        return True


class GithubWebhookEventSourceConfiguration(WebhookEventSourceConfig):
    """Configuration for github source filters."""

    webhook_secret: Optional[str] = SecretField()
    webhook_secret_id: Optional[UUID]


# -------------------- Github Webhook Plugin -----------------------------------


class GithubWebhookEventSourcePlugin(BaseWebhookEventSourcePlugin):
    """Handler for all github events."""

    @property
    def config_class(self) -> Type[GithubWebhookEventSourceConfiguration]:
        """Returns the `BasePluginConfig` config.

        Returns:
            The configuration.
        """
        return GithubWebhookEventSourceConfiguration

    @staticmethod
    def is_valid_signature(
        raw_body: bytes, secret_token: str, signature_header: str
    ) -> bool:
        """Verify that the payload was sent from GitHub by validating SHA256.

        Raise and return 403 if not authorized.

        Args:
            raw_body: original request body to verify (request.body())
            secret_token: GitHub app webhook token (WEBHOOK_SECRET)
            signature_header: header received from GitHub (x-hub-signature-256)

        Returns:
            Boolean if the signature is valid.
        """
        hash_object = hmac.new(
            secret_token.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        )
        expected_signature = "sha256=" + hash_object.hexdigest()

        if not hmac.compare_digest(expected_signature, signature_header):
            return False
        return True

    def _interpret_event(self, event: Dict[str, Any]) -> GithubEvent:
        """Converts the generic event body into a event-source specific pydantic model.

        Args:
            event: The generic event body

        Return:
            An instance of the event source specific pydantic model.

        Raises:
            ValueError: If the event body can not be parsed into the pydantic model.
        """
        try:
            event = GithubEvent(**event)
        except ValueError as e:
            logger.exception(e)
            # TODO: Remove this - currently useful for debugging
            with open(
                f'{datetime.now().strftime("%Y%m%d%H%M%S")}.json', "w"
            ) as f:
                json.dump(event, f)
            raise ValueError("Event did not match the pydantic model.")
        else:
            return event

    def _get_matching_triggers(
        self, event_source: EventSourceResponse, event: GithubEvent
    ) -> List[TriggerResponse]:
        """Get all Triggers with matching event filters.

        For github events this will compare the configured event filters
        of all matching triggers with the inbound event.

        Args:
            event_source: The event source.
            event: The inbound Event.

        Returns: A list of all matching Event Source IDs.
        """
        # get all event sources configured for this flavor
        triggers: List[TriggerResponse] = depaginate(
            partial(
                self.zen_store.list_triggers,
                trigger_filter_model=TriggerFilter(
                    event_source_id=event_source.id  # TODO: Handle for multiple source_ids
                ),
                hydrate=True,
            )
        )

        trigger_list: List[TriggerResponse] = []

        for trigger in triggers:
            event_filter = GithubWebhookEventFilterConfiguration(
                **trigger.metadata.event_filter
            )
            if event_filter.event_matches_filter(event=event):
                trigger_list.append(trigger)

        return trigger_list

    def _create_event_source(
        self, event_source: EventSourceRequest
    ) -> EventSourceResponse:
        """Wraps the zen_store creation method to add plugin specific functionality."""
        try:
            config = GithubWebhookEventSourceConfiguration(
                **event_source.configuration
            )
        except ValueError:
            raise ValueError("Event Source configuration invalid.")

        secret_key_value = random_str(12)
        webhook_secret = SecretRequest(
            name=f"event_source-{event_source.name}-{random_str(4)}".lower(),
            values={"webhook_secret": secret_key_value},
            workspace=event_source.workspace,
            user=event_source.user,
        )
        secret = self.zen_store.create_secret(webhook_secret)

        config.webhook_secret_id = secret.id
        event_source.configuration = config.dict()

        created_event_source = self.zen_store.create_event_source(
            event_source=event_source
        )
        created_event_source.metadata.configuration[
            "webhook_secret"
        ] = secret_key_value
        return created_event_source

    def _get_event_source(self, event_source_id: UUID) -> EventSourceResponse:
        """Wraps the zen_store getter method to add plugin specific functionality."""
        created_event_source = self.zen_store.get_event_source(
            event_source_id=event_source_id
        )
        webhook_secret_id = created_event_source.metadata.configuration[
            "webhook_secret_id"
        ]

        secret_value = self.zen_store.get_secret(
            secret_id=webhook_secret_id
        ).body["webhook_secret"]
        created_event_source.metadata.configuration[
            "webhook_secret"
        ] = secret_value
        return created_event_source
