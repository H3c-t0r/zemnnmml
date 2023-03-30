# Using a code repository

Code repositories enable ZenML to keep track of the code version that you use for your
pipeline runs. Additionally, running a pipeline which is tracked in a registered code
repository can speed up the Docker image building for containerized stack components.

## 📄 Prerequisites

In order to run your ZenML pipelines with a code repository, we need to set up a 
few things first:

* First you'll need a [GitHub](https://github.com) account and a GitHub repository
which contains code to run a ZenML pipeline. If you're new to ZenML and don't have such
a repository yet, we suggest you start by forking
[this example repository](https://github.com/zenml-io/code-repository-example) to get
started quickly. To do so, visit the repository page and click on `Fork` in the top right,
after which you'll be able to create a new fork in your personal GitHub account. Once that
is complete, clone the repository to your local machine.
* You'll also need to create a GitHub personal access token that has read permissions for
the repositories in your account. To do so, please follow [this guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) 
and make sure to assign your token the **repo** scope.

If you also want to test the Docker build speedup that is provided by using a
code repository, you'll additionally need:
* A remote ZenML deployment. See [here](https://docs.zenml.io/getting-started/deploying-zenml#deploying-zenml-in-the-cloud-remote-deployment-of-the-http-server-and-database) 
for more information on how to deploy ZenML.
* A remote stack with a containerized component like the
[`SagemakerOrchestrator`](https://docs.zenml.io/component-gallery/orchestrators/sagemaker)
or the [`VertexStepOperator`](https://docs.zenml.io/component-gallery/step-operators/vertex).

```bash
pip install zenml
zenml integration install github sklearn
zenml code-repository register <NAME> --type=github --owner=<GITHUB_USERNAME> \
    --repository=<REPOSITORY_NAME> --token=<PERSONAL_ACCESS_TOKEN>

# If you're testing the Docker build speedup, you need to connect to your remote
# ZenML deployment as well as register and activate your remote stack:
zenml connect --url=<ZENML_SERVER_URL>
zenml stack register <STACK_NAME> ...
zenml stack set <STACK_NAME>
```

## ▶️ Run the pipeline

To see the code repository in action, we will now run a ZenML pipeline for which the
code is stored in your code repository. If you're using a fork of the example repository,
you can run the pipeline by calling
```bash
python run.py
```

After that pipeline run has finished, we can inspect our pipeline run to see which code version
it was running with:
```python
from zenml.post_execution import get_pipeline

pipeline = get_pipeline("training_pipeline")
run = pipeline.runs[0]
print(run.commit)
```

## 🏎️ Testing the Docker build speedup

To see the Docker build speedup in action, we will start by modifying some of our pipeline
code. If you're using a fork of the example repository, you can for example change your
data loader step to have a different test set size:
```python
X_train, X_test, y_train, y_test = train_test_split(
    data, digits.target, test_size=0.1, shuffle=False  # test_size was 0.2 before
)
```

After you've finished modifying the code, we'll commit and push the changes:
```bash
git commit -am "Decrease test set size"
git push
```

Without a registered code repository, re-running the pipeline now would mean that ZenML
needs to build new Docker images that include your updated code. As we're running a pipeline
which is tracked inside a code repository, ZenML can instead download the updated code
when running the Docker container and can therefore reuse the previously built Docker images.

If we now re-run the pipeline by calling `python run.py`, we will see that no new
Docker images are being built and the old ones are being reused instead. This will not only
work on your local machine, but also if you're running the same pipeline from a different machine
or one of your colleagues tries to run the pipeline!

# 📜 Learn more

If you want to learn more about code repositories, check out our
[docs](https://docs.zenml.io/advanced-guide/practical-mlops/code-repositories).
