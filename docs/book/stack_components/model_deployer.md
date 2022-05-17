---
description: ...
---

Model deployers are stack components responsible for online model serving.
Online serving is the process of hosting and
loading machine-learning models as part of a managed web service and providing
access to the models through an API
endpoint like HTTP or GRPC. Once deployed, you can send inference requests to
the model through the web service's API
and receive fast, low-latency responses.

Add a model deployer to your ZenML stack to be able to implement continuous
model deployment pipelines that train models
and continuously deploy them to a model prediction web service.

When present in a stack, the model deployer also acts as a registry for models
that are served with ZenML. You can use
the model deployer to list all models that are currently deployed for online
inference or filtered according to a
particular pipeline run or step, or to suspend, resume or delete an external
model server managed through ZenML.

{% hint style="warning" %}
Before reading this chapter, make sure that you are familiar with the 
concept of [stacks, stack components and their flavors](./introduction.md).  
{% endhint %}

## Base Abstraction

WIP

## List of available .......

WIP

## Building your own .......

WIP

