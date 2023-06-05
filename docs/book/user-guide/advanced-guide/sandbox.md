---
description: Running pipelines in the MLOps Platform Sandbox.
---

# Use the Sandbox

The [MLOps Platform Sandbox](https://sandbox.zenml.io) is a temporary MLOps platform that includes ZenML, [MLflow](https://mlflow.org), [Kubeflow](https://www.kubeflow.org/), and [Minio](https://min.io/). Its purpose is to showcase the simplicity of creating a production-ready machine-learning solution using popular open-source tools. The Sandbox is designed for learning and experimentation, not for commercial projects or large-scale production use. It offers users a controlled environment to explore MLOps tools and processes before building their custom MLOps stack based on their specific requirements.

## How does the Sandbox work?

After signing up, a user "creates a sandbox" which provisions the following services on a cluster managed by the ZenML team:

* [MLflow](https://mlflow.org): An [experiment tracker](../component-guide/experiment-trackers/experiment-trackers.md) for tracking metadata.
* [Kubeflow](https://kubeflow.org): An [orchestrator](../component-guide/orchestrators/orchestrators.md) for running ML workloads on Kubernetes.
* [Minio](https://min.io/): An [artifact store](../component-guide/artifact-stores/artifact-stores.md) for storing artifacts produced by pipelines.
* [ZenML](https://zenml.io): The MLOps framework that integrates everything.

Each sandbox comes with limited computing and storage resources. The ZenML service included with each sandbox has the following features:

* A [registered stack with other services](../starter-guide/understand-stacks.md), including all credentials as [secrets](../../platform-guide/set-up-your-mlops-platform/use-the-secret-store/use-the-secret-store.md).
* A set of an example pipeline [execution environment builds](manage-environments.md#execution-environments). These Docker images are hosted on Dockerhub and make running the example pipelines easy.
* A connected [code repository](connect-your-git-repository.md) containing the code for the example pipelines. This repository is the official ZenML repository (with the code located in the [examples](https://github.com/zenml-io/zenml/tree/main/examples) directory).

In order to run the example pipelines, users need to download the repository locally and execute a pipeline with a supported build. The Sandbox UI offers a convenient interface for copying the relevant commands. The [starter guide](../starter-guide/switch-to-production.md) also provides more details on running these example pipelines.

![ZenML Sandbox Gitbook commands](/docs/book/.gitbook/assets/zenml_sandbox_step_3_commands.png)

## How do I use the Sandbox to run custom pipelines?

As discussed above, the sandbox provides pre-built pipelines for users to run.
If you want to try running these pipelines first, please [visit this
page](../starter-guide/switch-to-production.md) in the starter guide to learn
how to do this. The limitation on running custom pipelines is in place to
control costs and demonstrate how MLOps engineers can enforce rules through a
central control plane.

You might nevertheless be interested in using the resources provisioned in the Sandbox to run your own pipelines. There are two ways to do this:

### Run pipelines without custom dependencies

If you have code that uses the same dependencies as the ones provided in the examples docs, you can simply update the example pipeline code (or even add new pipelines) by pushing to a git repository, and reusing existing [environment builds](containerize-your-pipeline.md#reuse-docker-image-builds-from-previous-runs) of the example pipelines.

Of course, in order to be able to do that, you need to be able to push to the code repository. You can either:

* Fork the zenml repository, so that the examples directory is within your code, and you can edit it in your fork, or
* Create a new code repository with a new token that allows you to push. You can then copy the examples code into your new code repository, and edit it.

Read more about how to connect a git repository to ZenML [here](connect-your-git-repository.md).

After that is done, you can change the code and run the pipeline with your chosen execution environment build. Learn more about reusing execution environments [here](containerize-your-pipeline.md#reuse-docker-image-builds-from-previous-runs).

### Run pipelines with custom dependencies

If you have code with custom dependencies than the ones in the sandbox examples,
you need to copy the stack provided in the sandbox and swap the container
registry with a public container registry that you have `write` access to. The
[container registry stack component
pages](../component-guide/container-registries/container-registries.md) talk
more about how to do this.

To register a new stack, you can execute the following:

```shell
zenml stack register my_stack \
  -o sandbox-kubeflow \
  -a sandbox-minio \
  -e sandbox-mlflow \
  -dv sandbox-validator \
  -c <MY_CONTAINER_REGISTRY> \
  --set
```

With the above stack, you can run whatever code you'd like without tying it to a container registry because ZenML will just build and push Docker images to your container registry from your local client.

## What to do when your sandbox runs out?

The Sandbox will only run for 8 hours. After that, it will be deleted. If you want to continue to use ZenML in a cloud deployment you can either:

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead><tbody><tr><td><mark style="color:purple;"><strong>Register a new Sandbox</strong></mark></td><td>Create and utilize a brand new Sandbox instance</td><td><a href="https://sandbox.zenml.io">https://sandbox.zenml.io</a></td></tr><tr><td><mark style="color:purple;"><strong>Extend your Sandbox time limit</strong></mark></td><td>Fill out a form to extend the time limit of your Sandbox instances</td><td><a href="https://zenml.io/extend-sandbox">https://zenml.io/extend-sandbox</a></td></tr><tr><td><mark style="color:purple;"><strong>Deploy your own cloud stack</strong></mark></td><td>Deploy and use a stack on a cloud environment</td><td><a href="../../platform-guide/set-up-your-mlops-platform/deploy-and-set-up-a-cloud-stack/deploy-a-stack-post-sandbox.md">deploy-a-stack-post-sandbox.md</a></td></tr></tbody></table>
