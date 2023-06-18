---
description: Configuring pipelines, steps, and stack components in ZenML.
---

# Configure steps/pipelines

## Parameters for your steps

When calling a step in a pipeline, the inputs provided to the step function can either be an **artifact** or a **parameter**. An artifact represents the output of another step that was executed as part of the same pipeline and serves as a means to share data between steps. Parameters, on the other hand, are values provided explicitly when invoking a step. They are not dependent on the output of other steps and allow you to parameterize the behavior of your steps.

{% hint style="info" %}
In order to allow the configuration of your steps using a configuration file, only values that can be serialized to JSON using Pydantic can be passed as parameters.
{% endhint %}

```python
@step
def my_step(input_1: int, input_2: int) -> None:
    pass


@pipeline
def my_pipeline():
    int_artifact = some_other_step()
    # We supply the value of `input_1` as an artifact and
    # `input_2` as a parameter
    my_step(input_1=int_artifact, input_2=17)
    # We could also call the step with two artifacts or two
    # parameters instead:
    # my_step(input_1=int_artifact, input_2=int_artifact)
    # my_step(input_1=1, input_2=2)
```

**Parameters and caching**

When an input is passed as a parameter, the step will only be cached if all parameter values are exactly the same as for previous executions of the step.

**Artifacts and caching**

When an artifact is used as a step function input, the step will only be cached if all the artifacts are exactly the same as for previous executions of the step. This means that if any of the upstream steps that produce the input artifacts for a step were not cached, the step itself will always be executed.

## Pass any kind of data to your steps

**External artifacts** can be used to pass values to steps that are neither JSON serializable nor produced by an upstream step.

```python
import numpy as np
from zenml import pipeline, step
from zenml.steps.external_artifact import ExternalArtifact

@step
def trainer(data: np.ndarray) -> ...:
    ...

@pipeline
def my_pipeline():
    trainer(data=ExternalArtifact(np.array([1, 2, 3])))

    # This would not work, as only JSON serializable values
    # or artifacts can be passed as a step input:
    # trainer(data=np.array([1, 2, 3]))
```

Optionally, you can configure the `ExternalArtifact` to use a custom [materializer](handle-custom-data-types.md) for your data or disabled artifact metadata and visualizations. Check out the [API docs](https://apidocs.zenml.io/latest/core\_code\_docs/core-steps/#zenml.steps.external\_artifact.ExternalArtifact) for all available options.

{% hint style="info" %}
Using an `ExternalArtifact` with input data for your step automatically disables caching for the step.
{% endhint %}

You can also use an `ExternalArtifact` to pass an artifact stored in the ZenML database:

```python
from uuid import UUID

artifact = ExternalArtifact(id=UUID("3a92ae32-a764-4420-98ba-07da8f742b76"))
```

## Control the execution order

By default, ZenML uses the data flowing between steps of your pipeline to determine the order in which steps get executed.&#x20;

The following example shows a pipeline in which `step_3` depends on the outputs of `step_1` and `step_2`. This means that ZenML can execute both `step_1` and `step_2` in parallel but needs to wait until both are finished before `step_3` can be started.

```python
from zenml.pipelines import pipeline

@pipeline
def example_pipeline():
    step_1_output = step_1()
    step_2_output = step_2()
    step_3(step_1_output, step_2_output)
```

If you have additional constraints on the order in which steps get executed, you can specify non-data dependencies by calling `step.after(some_other_step)`:

```python
from zenml.pipelines import pipeline

@pipeline
def example_pipeline():
    step_1.after(step_2)
    step_1_output = step_1()
    step_2_output = step_2()
    step_3(step_1_output, step_2_output)
```

This pipeline is similar to the one explained above, but this time ZenML will make sure to only start `step_1` after `step_2` has finished.

## Settings in ZenML

Settings in ZenML allow you to configure runtime configurations for stack components and pipelines. Concretely, they allow you to configure:

* The [resources](scale-compute-to-the-cloud.md#specify-resource-requirements-for-steps) required for a step
* Configuring the [containerization](containerize-your-pipeline.md) process of a pipeline (e.g. What requirements get installed in the Docker image)
* Stack component-specific configuration, e.g., if you have an experiment tracker passing in the name of the experiment at runtime

You will learn about all of the above in more detail later, but for now, let's try to understand that all of this configuration flows through one central concept, called `BaseSettings` (From here on, we use `settings` and `BaseSettings` as analogous in this guide).

### Types of settings

Settings are categorized into two types:

* **General settings** that can be used on all ZenML pipelines. Examples of these are:
  * [`DockerSettings`](containerize-your-pipeline.md) to specify docker settings.
  * [`ResourceSettings`](scale-compute-to-the-cloud.md#specify-resource-requirements-for-steps) to specify resource settings.
* **Stack-component-specific settings**: These can be used to supply runtime configurations to certain stack components (key= \<COMPONENT\_CATEGORY>.\<COMPONENT\_FLAVOR>). Settings for components not in the active stack will be ignored. Examples of these are:
  * [`KubeflowOrchestratorSettings`](../component-guide/orchestrators/kubeflow.md) to specify Kubeflow settings.
  * [`MLflowExperimentTrackerSettings`](../component-guide/experiment-trackers/mlflow.md) to specify MLflow settings.
  * [`WandbExperimentTrackerSettings`](../component-guide/experiment-trackers/wandb.md) to specify W\&B settings.
  * [`WhylogsDataValidatorSettings`](../component-guide/data-validators/whylogs.md) to specify Whylogs settings.

For stack-component-specific settings, you might be wondering what the difference is between these and the configuration passed in while doing `zenml stack-component register <NAME> --config1=configvalue --config2=configvalue`, etc. The answer is that the configuration passed in at registration time is static and fixed throughout all pipeline runs, while the settings can change.

A good example of this is the [`MLflow Experiment Tracker`](../component-guide/experiment-trackers/mlflow.md), where configuration which remains static such as the `tracking_url` is sent through at registration time, while runtime configuration such as the `experiment_name` (which might change every pipeline run) is sent through as runtime settings.

Even though settings can be overridden at runtime, you can also specify _default_ values for settings while configuring a stack component. For example, you could set a default value for the `nested` setting of your MLflow experiment tracker: `zenml experiment-tracker register <NAME> --flavor=mlflow --nested=True`

This means that all pipelines that run using this experiment tracker use nested MLflow runs unless overridden by specifying settings for the pipeline at runtime.

{% embed url="https://www.youtube.com/embed/AdwW6DlCWFE" %}
Stack Component Config vs Settings in ZenML
{% endembed %}

#### Using objects or dicts

Settings can be passed in directly as BaseSettings-subclassed objects, or a dictionary representation of the object. For example, a Docker configuration can be passed in as follows:

```python
from zenml.config import DockerSettings

settings = {'docker': DockerSettings(requirements=['pandas'])}
```

Or like this:

```python
settings = {'docker': {'requirements': ['pandas']}}
```

### Utilizing the settings

#### Method 1: Directly on the decorator

The most basic way to set settings is through the `settings` variable that exists in both `@step` and `@pipeline` decorators:

```python
@step(settings=...)


...


@pipeline(settings=...)


...
```

{% hint style="info" %}
Once you set settings on a pipeline, they will be applied to all steps with some exceptions. See the [later section on precedence for more details](configure-steps-pipelines.md#hierarchy-and-precedence).
{% endhint %}

#### Method 2: On the step/pipeline instance

This is exactly the same as passing it through the decorator, but if you prefer you can also pass it in the `configure` methods of the pipeline and step instances:

```python
@step
def my_step() -> None:
    print("my step")


@pipeline
def my_pipeline():
    my_step()


# Same as passing it in the step decorator
my_step.configure(settings=...)

# Same as passing it in the pipeline decorator
my_pipeline.configure(settings=...)
```

#### Method 3: Configuring with YAML

As all settings can be passed through as a dictionary, users have the option to send all configurations in via a YAML file. This is useful in situations where code changes are not desirable.

To use a YAML file, you must pass it in the `run` method of a pipeline instance:

```python
@step
def my_step() -> None:
    print("my step")


@pipeline
def my_pipeline():
    my_step()


# Pass in a config file
my_pipeline = my_pipeline.with_options(config_path='/local/path/to/config.yaml')
```

The format of a YAML config file is exactly the same as the dictionary you would pass in Python in the above two sections. The step-specific settings are nested in a key called `steps`. Here is a rough skeleton of a valid YAML config. All keys are optional.

```yaml
enable_cache: True
enable_artifact_metadata: True
enable_artifact_visualization: True
extra:
  tags: production
run_name: my_run
schedule: { }
settings: { }  # same as pipeline settings
steps:
  name_of_step_1:
    settings: { }  # same as step settings
  name_of_step_2:
    settings: { }
  ...
```

ZenML provides a convenient method that takes a pipeline instance and generates a config template based on its settings automatically:

```python
my_pipeline.write_run_configuration_template(path='/local/path/to/config.yaml')
```

This will write a template file at `/local/path/to/config.yaml` with a commented-out YAML file with all possible options that the pipeline instance can take.

Here is an example of a YAML config file generated from the above method:

<details>

<summary>An example of a YAML config</summary>

Some configuration is commented out as it is not needed.

```yaml
enable_cache: True
enable_artifact_metadata: True
enable_artifact_visualization: True
extra:
  tags: production
run_name: my_run
# schedule:
#   catchup: bool
#   cron_expression: Optional[str]
#   end_time: Optional[datetime]
#   interval_second: Optional[timedelta]
#   start_time: Optional[datetime]
settings:
  docker:
    build_context_root: .
    # build_options: Mapping[str, Any]
    # source_files: str
    # copy_global_config: bool
    # dockerfile: Optional[str]
    # dockerignore: Optional[str]
    # environment: Mapping[str, Any]
    # install_stack_requirements: bool
    # parent_image: Optional[str]
    # replicate_local_python_environment: Optional
    # required_integrations: List[str]
    requirements:
      - pandas
    # target_repository: str
    # user: Optional[str]
  resources:
    cpu_count: 1
    gpu_count: 1
    memory: "1GB"
steps:
  # get_first_num:
  enable_cache: false
  experiment_tracker: mlflow_tracker
  # extra: Mapping[str, Any]
  # outputs:
  #   first_num:
  #     artifact_source: Optional[str]
  #     materializer_source: Optional[str]
  # parameters: {}
  # settings:
  #   resources:
  #     cpu_count: Optional[PositiveFloat]
  #     gpu_count: Optional[PositiveInt]
  #     memory: Optional[ConstrainedStrValue]
  # step_operator: Optional[str]
  # get_random_int:
  #   enable_cache: Optional[bool]
  #   experiment_tracker: Optional[str]
  #   extra: Mapping[str, Any]
  #   outputs:
  #     random_num:
  #       artifact_source: Optional[str]
  #       materializer_source: Optional[str]
  #   parameters: {}
  #   settings:
  #     resources:
  #       cpu_count: Optional[PositiveFloat]
  #       gpu_count: Optional[PositiveInt]
  #       memory: Optional[ConstrainedStrValue]
  #   step_operator: Optional[str]
  # subtract_numbers:
  #   enable_cache: Optional[bool]
  #   experiment_tracker: Optional[str]
  #   extra: Mapping[str, Any]
  #   outputs:
  #     result:
  #       artifact_source: Optional[str]
  #       materializer_source: Optional[str]
  #   parameters: {}
  #   settings:
  #     resources:
  #       cpu_count: Optional[PositiveFloat]
  #       gpu_count: Optional[PositiveInt]
  #       memory: Optional[ConstrainedStrValue]
  #   step_operator: Optional[str]

```

</details>

### The `extra` dict

You might have noticed another dictionary that is available to be passed to steps and pipelines called `extra`. This dictionary is meant to be used to pass any configuration down to the pipeline, step, or stack components that the user has use of.

An example of this is if I want to tag a pipeline, I can do the following:

```python
@pipeline(name='my_pipeline', extra={'tag': 'production'})


...
```

This tag is now associated and tracked with all pipeline runs, and can be fetched later with the [post-execution workflow](../starter-guide/fetch-runs-after-execution.md):

```python
from zenml.post_execution import get_pipeline

p = get_pipeline('my_pipeline')

# print out the extra
print(p.runs[0].pipeline_configuration['extra'])
# {'tag': 'production'}
```

### Hierarchy and precedence

Some settings can be configured on pipelines and steps, some only on one of the two. Pipeline-level settings will be automatically applied to all steps, but if the same setting is configured on a step as well that takes precedence. The next section explains in more detail how the step-level settings will be merged with pipeline settings.

### Merging settings on instance/run:

When a settings object is configured, ZenML merges the values with previously configured keys. E.g.:

```python
from zenml.config import ResourceSettings


@step(settings={"resources": ResourceSettings(cpu_count=2, memory="1GB")})
def my_step() -> None:
    ...


my_step.configure(
    settings={"resources": ResourceSettings(gpu_count=1, memory="2GB")}
)

my_step.configuration.settings["resources"]
# cpu_count: 2, gpu_count=1, memory="2GB"
```

In the above example, the two settings were automatically merged.

<!-- For scarf -->
<figure><img alt="ZenML Scarf" referrerpolicy="no-referrer-when-downgrade" src="https://static.scarf.sh/a.png?x-pxid=f0b4f458-0a54-4fcd-aa95-d5ee424815bc" /></figure>
