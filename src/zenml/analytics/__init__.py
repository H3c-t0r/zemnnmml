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

from zenml.analytics.client import Client

"""Settings."""
on_error = Client.DefaultConfig.on_error
debug = Client.DefaultConfig.debug
send = Client.DefaultConfig.send
sync_mode = Client.DefaultConfig.sync_mode
max_queue_size = Client.DefaultConfig.max_queue_size
gzip = Client.DefaultConfig.gzip
timeout = Client.DefaultConfig.timeout
max_retries = Client.DefaultConfig.max_retries


def track(*args, **kwargs):
    """Send a track call."""
    _proxy("track", *args, **kwargs)


def identify(*args, **kwargs):
    """Send a identify call."""
    _proxy("identify", *args, **kwargs)


def group(*args, **kwargs):
    """Send a group call."""
    _proxy("group", *args, **kwargs)


def alias(*args, **kwargs):
    """Send a alias call."""
    _proxy("alias", *args, **kwargs)


def page(*args, **kwargs):
    """Send a page call."""
    _proxy("page", *args, **kwargs)


def screen(*args, **kwargs):
    """Send a screen call."""
    _proxy("screen", *args, **kwargs)


def flush():
    """Tell the client to flush."""
    _proxy("flush")


def join():
    """Block program until the client clears the queue"""
    _proxy("join")


def shutdown():
    """Flush all messages and cleanly shutdown the client"""
    _proxy("flush")
    _proxy("join")


default_client = None


def _proxy(method, *args, **kwargs):
    """Create an analytics client if one doesn't exist and send to it."""
    global default_client
    if not default_client:
        default_client = Client(
            debug=debug,
            max_queue_size=max_queue_size,
            send=send,
            on_error=on_error,
            gzip=gzip,
            max_retries=max_retries,
            sync_mode=sync_mode,
            timeout=timeout,
        )

    fn = getattr(default_client, method)
    fn(*args, **kwargs)
