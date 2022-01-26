#  Copyright (c) ZenML GmbH 2021. All Rights Reserved.
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

""" Plugin which is created to add Google Cloud Store support to ZenML.
It inherits from the base Filesystem created by TFX and overwrites the
corresponding functions thanks to gcsfs.
"""


import gcsfs

from zenml.io.cloud_filesystem import CloudFilesystem


class ZenGCS(CloudFilesystem):
    """Filesystem that delegates to Google Cloud Store using gcsfs."""

    SUPPORTED_SCHEMES = ["gs://"]
    fs: gcsfs.GCSFileSystem = None

    @classmethod
    def _ensure_filesystem_set(cls) -> None:
        """Ensures that the filesystem is set."""
        if cls.fs is None:
            cls.fs = gcsfs.GCSFileSystem()
