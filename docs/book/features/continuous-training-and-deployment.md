---
description: Implement end-to-end ML workflows with Continuous Training and Deployment.
---

# Continuous Training and Continuous Deployment (CT/CD)

As an organization develops across the [MLOps maturity model](https://docs.microsoft.com/en-us/azure/architecture/example-scenario/mlops/mlops-maturity-model), 
the terms Continuous Training and Continuous Deployment (CT/CD) get more relevant.

- Continuous Training refers to the paradigm where a team deploy training pipelines that run automatically to train models on
new (fresh) data. (e.g. Every two weeks, take the latest data from an API, and train a new model on it.)
- Continuous Deployment refers to the paradigm where a newly trained models are automatically deployed to a prediction 
service/server, when a criterion in production is fulfilled (e.g. if a trained model has a certain accuracy, or overall performs better than the previous one, deploy it in production.)

ZenML allows both paradigms with [Schedules](../introduction/core-concepts.md), [Model Deployers](../introduction/core-concepts.md#model-deployer) and [Services](../introduction/core-concepts.md#service).

## Setting a pipeline schedule for Continuous Training (CT)

ZenML supports running pipelines on a schedule as follows:

```python
import datetime
from datetime import timedelta
from zenml.pipelines import Schedule

# Create a schedule to run a pipeline every minute for the next ten minutes
schedule = Schedule(
    start_time=datetime.now(),
    end_time=datetime.now() + timedelta(minutes=10),
    interval_second=60,
)

# Run the pipeline on a schedule
my_pipeline(
    ...  # steps
).run(schedule=schedule)
```

The above deploys a pipeline, potentially on a [production stack](guide-aws-gcp-azure.md), on a defined schedule. If the 
pipeline has a well-defined data loading/importing step, then one can deploy it to run and train new models on fresh data 
on a regular basis. This enables Continuous Training with ZenML.

## Interacting with services for Continuous Deployment (CD)

Continuous Training is necessary in a mature MLOps setting, but Continuous Deployment completes the picture. Continuous Deployment 
is also interesting because it involves interacting with systems that are longer-lived than a pipeline run.

ZenML interacts with such external systems (e.g. like prediction servers) through
the `Model Deployer` abstraction. The concrete implementation of this abstraction
deals with functionality concerning the life-cycle management and tracking of
external model deployment servers (e.g. process, container, Kubernetes deployment etc.),
which are represented in ZenML using another abstraction: `Services`.

The first thing needed to be able to deploy machine learning models to external
model serving platforms with ZenML in a continuous deployment manner is to have
a Model Deployer registered as part of your ZenML Stack. The Seldon Core Model
Deployer is one example of a Model Deployer already provided by ZenML as an
integration, MLflow is coming up next and other Model Deployers will follow.

There are three major roles that a Model Deployer plays in a ZenML Stack:

1. it holds all the stack related configuration attributes required to
interact with the remote model serving tool, service or platform (e.g.
hostnames, URLs, references to credentials, other client related
configuration parameters). This is an example of configuring the Seldon Core
Model Deployer and registering it as a Stack component:

    ```bash
    zenml model-deployer register seldon --type=seldon \
    --kubernetes_context=zenml-eks --kubernetes_namespace=zenml-workloads \
    --base_url=http://abb84c444c7804aa98fc8c097896479d-377673393.us-east-1.elb.amazonaws.com
    ...
    zenml stack register seldon_stack -m default -a aws -o default -d seldon
    ```

2. it implements the continuous deployment logic necessary to deploy models
in a way that updates an existing model server that is already serving a
previous version of the same model instead of creating a new model server
for every new model version. Every model server that the Model Deployer
provisions externally to deploy a model is represented internally as a
`Service` object that may be accessed to for visibility and control over
a single model deployment. This functionality can be consumed directly
from ZenML pipeline steps, but it can also be used outside of the pipeline
to deploy ad-hoc models. The following code is an example of using the
Seldon Core Model Deployer to deploy a model inside a ZenML pipeline step:

    ```python
    from zenml.environment import Environment
    from zenml.integrations.seldon.model_deployers import SeldonModelDeployer
    from zenml.integrations.seldon.services.seldon_deployment import (
        SeldonDeploymentConfig,
        SeldonDeploymentService,
    )
    from zenml.steps import (
        STEP_ENVIRONMENT_NAME,
        BaseStepConfig,
        StepEnvironment,
        step,
    )

    @step(enable_cache=True)
    def seldon_model_deployer_step(
        context: StepContext,
        model: ModelArtifact,
    ) -> SeldonDeploymentService:
        model_deployer = SeldonModelDeployer.get_active_model_deployer()

        # get pipeline name, step name and run id
        step_env = Environment()[STEP_ENVIRONMENT_NAME])

        service_config=SeldonDeploymentConfig(
            model_uri=model.uri,
            model_name="my-model",
            replicas=1,
            implementation="TENSORFLOW_SERVER",
            secret_name="seldon-secret",
            pipeline_name = step_env.pipeline_name,
            pipeline_run_id = step_env.pipeline_run_id,
            pipeline_step_name = step_env.step_name,
        )

        service = model_deployer.deploy_model(
            service_config, replace=True, timeout=300
        )

        print(
            f"Seldon deployment service started and reachable at:\n"
            f"    {service.prediction_url}\n"
        )

        return service
    ```

3. the Model Deployer acts as a registry for all Services that represent remote
model servers. External model deployment servers can be queried using a variety
of criteria, such as the name of the model or the names of the pipeline and step
that was used to deploy it. The Service objects returned by the Model Deployer
can be used to interact with the remote model server, e.g. to get the operational
status of a model server, the prediction URI that it exposed, or to stop or
delete a model server:

    ```python
    from zenml.integrations.seldon.model_deployers import SeldonModelDeployer

    model_deployer = SeldonModelDeployer.get_active_model_deployer()
    services = model_deployer.find_model_server(
        pipeline_name="continuous-deployment-pipeline",
        pipeline_step_name="seldon_model_deployer_step",
        model_name="my-model",
    )
    if services:
        if services[0].is_running:
            print(
                f"Seldon deployment service started and reachable at:\n"
                f"    {service.prediction_url}\n"
            )
        elif services[0].is_failed:
            print(
                f"Seldon deployment service is in a failure state. "
                f"The last error message was: {service.status.last_error}"
            )
        else:
            print(f"Seldon deployment service is not running")

            # start the service
            services[0].start(timeout=100)

        # delete the service
        model_deployer.delete_service(services[0].uuid, timeout=100, force=False)
    ```

When a Model Deployer is part of the active ZenML Stack, it is also possible to
interact with it from the CLI to list, start, stop or delete the model servers
that is manages:

```bash
$ zenml served-models list
┏━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ STATUS │ UUID                                 │ PIPELINE_NAME                  │ PIPELINE_STEP_NAME         ┃
┠────────┼──────────────────────────────────────┼────────────────────────────────┼────────────────────────────┨
┃   ✅   │ 8cbe671b-9fce-4394-a051-68e001f92765 │ continuous_deployment_pipeline │ seldon_model_deployer_step ┃
┗━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

$ zenml served-models describe 8cbe671b-9fce-4394-a051-68e001f92765
                          Properties of Served Model 8cbe671b-9fce-4394-a051-68e001f92765                          
┏━━━━━━━━━━━━━━━━━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ MODEL SERVICE PROPERTY │ VALUE                                                                                  ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ MODEL_NAME             │ mnist                                                                                  ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ MODEL_URI              │ s3://zenfiles/seldon_model_deployer_step/output/884/seldon                             ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ PIPELINE_NAME          │ continuous_deployment_pipeline                                                         ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ PIPELINE_RUN_ID        │ continuous_deployment_pipeline-11_Apr_22-09_39_27_648527                               ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ PIPELINE_STEP_NAME     │ seldon_model_deployer_step                                                             ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ PREDICTION_URL         │ http://abb84c444c7804aa98fc8c097896479d-377673393.us-east-1.elb.amazonaws.com/seldon/… ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ SELDON_DEPLOYMENT      │ zenml-8cbe671b-9fce-4394-a051-68e001f92765                                             ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ STATUS                 │ ✅                                                                                     ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ STATUS_MESSAGE         │ Seldon Core deployment 'zenml-8cbe671b-9fce-4394-a051-68e001f92765' is available       ┃
┠────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┨
┃ UUID                   │ 8cbe671b-9fce-4394-a051-68e001f92765                                                   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

$ zenml served-models get-url 8cbe671b-9fce-4394-a051-68e001f92765
  Prediction URL of Served Model 8cbe671b-9fce-4394-a051-68e001f92765 is:
  http://abb84c444c7804aa98fc8c097896479d-377673393.us-east-1.elb.amazonaws.com/seldon/zenml-workloads/zenml-8cbe67
1b-9fce-4394-a051-68e001f92765/api/v0.1/predictions

$ zenml served-models delete 8cbe671b-9fce-4394-a051-68e001f92765
```

Services can be passed through steps like any other object, and used to interact with the external systems that
they represent:

```python
@step
def my_step(my_service: MyService) -> ...:
    if not my_service.is_running:
        my_service.start() # starts service
    my_service.stop()  # stops service
```

You can see a concrete example of using a Model Deployer to implement a continuous
training and continuous deployment pipeline with the
[Seldon Core deployment example](https://github.com/zenml-io/zenml/tree/main/examples/seldon_deployment).

Another concrete example of a pipeline step that uses a model deployment `Service` implementation is the `MLFlowDeploymentService`.
It enables serving models with MLflow deployment server instances, also running locally as daemon processes.

When inserted into a pipeline, a service like the MLflow service takes care of all the aspects of continuously deploying models to an external server. 
E.g. In the MLflow integration, there is a standard `MLflowDeployerStep` that creates and continuously updates the prediction server to deploy the latest 
model. All we need to do is add it as a deployer step to our pipeline and provide it with the name of the model to deploy:

```python
model_deployer = mlflow_deployer_step() 

# Initialize a continuous deployment pipeline run
deployment = continuous_deployment_pipeline(
    ...
    model_deployer=model_deployer(config=MLFlowDeployerConfig(model_name="my_model", workers=3)),
)
```

This service can also be used to interact with a model prediction server with the following interface:

```python
my_deployment_service.predict(my_data)  # sends data to prediction service with a unified interface
```

You can see a concrete example of using Services in a continuous training and continuous deployment setting with the 
[MLflow deployment example](https://github.com/zenml-io/zenml/tree/main/examples/mlflow_deployment).