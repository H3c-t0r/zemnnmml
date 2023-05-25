# How to Write an Integration Example

## 🥅 Our Goals for the examples

- First touchpoint for the user with the integration
- Location for copy-pasting integration specific code
- Integration testing
- Place for us to play around during development of additional features

## 📝 Write the Example

![KISS](assets/KISS.png)

Remember to keep it simple. That's what we're going for with these examples.
Avoid unnecessary dependencies, unnecessary configuration parameters and
unnecessary code complexity in general.

### 🖼 This is what a minimal example could look like

This way the example stays as simple as possible, while showing how to create a
custom materializer. We have a minimal object
to materialize, we have a minimal pipeline that shows a step that produces this
object and a step that consumes the
object.

```python
import logging
import os
from typing import Type

from zenml import step, pipeline

from zenml import step, pipeline
from zenml.enums import ArtifactType
from zenml.io import fileio
from zenml.materializers.base_materializer import BaseMaterializer


class MyObj:
    def __init__(self, name: str):
        self.name = name


class MyMaterializer(BaseMaterializer):
    ASSOCIATED_TYPES = (MyObj,)
    ASSOCIATED_ARTIFACT_TYPE = ArtifactType.DATA

    def load(self, data_type: Type[MyObj]) -> MyObj:
        """Read from artifact store."""
        with fileio.open(os.path.join(self.uri, 'data.txt'), 'r') as f:
            name = f.read()
        return MyObj(name=name)

    def save(self, my_obj: MyObj) -> None:
        """Write to artifact store."""
        with fileio.open(os.path.join(self.uri, 'data.txt'), 'w') as f:
            f.write(my_obj.name)


@step
def my_first_step() -> MyObj:
    """Step that returns an object of type MyObj."""
    return MyObj("my_object")

my_first_step = my_first_step.configure(output_materializers=MyMaterializer)

# (Optional) tell ZenML to use your custom materializer for this step.
# This is usually not needed since ZenML automatically discovers materializers
# and determines which one to use based on the data type of your output
step1.configure(output_materializers=MyMaterializer)


@step
def my_second_step(my_obj: MyObj) -> None:
    """Step that log the input object and returns nothing."""
    logging.info(
        f"The following object was passed to this step: `{my_obj.name}`")


@pipeline
def first_pipeline():
    output_1 = my_first_step()
    my_second_step(output_1)

if __name__ == "__main__":
    first_pipeline()
```

## 📰 Write the Readme

[Here](template_README.md) is a template. Make sure to replace everything in
square brackets. Depending on your specific
example feel free to add or remove sections where appropriate.

## (Optional) Create a requirements.txt

In case your example has Python requirements that are not ZenML integrations you
can also add a `requirements.txt`
file with these packages.

## ⚙️ (Optional) Create setup.sh

The `setup.sh` file is necessary to support the `zenml example run` cli command.
Within the `setup.sh` file you'll need to define what
ZenML integrations need to be installed. Find the
template [here](template_setup.sh). In case your example needs more
user-specific setup, like a tool, specific account or system requirement, you **
should not** create a setup.sh. In this
case the `zenml example run <EXAMPLE NAME>` won't be supported.

### 🧪 Test ZenML Example CLI

Our `example` CLI commands serve as a super quick entrypoint for users. As such
it is important to make sure your new
example can be executed with the following command:

```shell
zenml example pull
zenml example run <EXAMPLE NAME>
```

This will pull examples from the latest release, copy them to your current
working directory and run it using the
[run_example.sh](../run_example.sh).

However, this only works with branches on the main ZenML Github repository. In
order to validate your example, navigate
into the examples folder and run the following command:

```shell
./run_example.sh --executable <NAME_OF_YOUR_EXAMPLE>/run.py
```

## ➕ Add to main README file

In the [main README](../README.md), make sure to add your example to the correct
cluster or create a new cluster with a
description if your integration does not fit the preexisting ones.
