# 🛤️ Track experiments with MLflow Tracking

[MLflow Tracking](https://www.mlflow.org/docs/latest/tracking.html) is a popular
tool that tracks and visualizes experiment runs with their many parameters,
metrics and output files.

## 🗺 Overview

This example showcases how easily mlflow tracking can be integrated into a ZenML pipeline with just a few simple lines
of code.

We'll be using the
[Fashion-MNIST](https://github.com/zalandoresearch/fashion-mnist) dataset and
will train a classifier using [Tensorflow (Keras)](https://www.tensorflow.org/).
We will run two experiments with different parameters (epochs and learning rate)
and log these experiments into a local mlflow backend.

This example uses an mlflow setup that is based on the local filesystem for
things like the artifact store. See the [mlflow
documentation](https://www.mlflow.org/docs/latest/tracking.html#scenario-1-mlflow-on-localhost) 
for details.

In the example script the [mlflow autologger for
Keras](https://www.mlflow.org/docs/latest/tracking.html#tensorflow-and-keras) is
used within the training step to directly hook into the TensorFlow training and
it will log out all relevant parameters, metrics and output files. Additionally,
we explicitly log the test accuracy within the evaluation step.

This example uses an mlflow setup that is based on the local filesystem as
orchestrator and artifact store. See the [mlflow
documentation](https://www.mlflow.org/docs/latest/tracking.html#scenario-1-mlflow-on-localhost)
for details.

# 🖥 Run it locally

## ⏩ SuperQuick `mlflow_tracking` run

If you're really in a hurry, and you want just to see this example pipeline run,
without wanting to fiddle around with all the individual installation and
configuration steps, just run the following:

```shell
zenml example run mlflow_tracking
```

## 👣 Step-by-Step
### 📄 Prerequisites 
In order to run this example, you need to install and initialize ZenML:

```shell
# install CLI
pip install zenml

# install ZenML integrations
zenml integration install mlflow
zenml integration install tensorflow

# pull example
zenml example pull mlflow_tracking
cd zenml_examples/mlflow_tracking

# initialize
zenml init
```

### ▶️ Run the Code
Now we're ready. Execute:

```bash
python run.py
```

### 🔮 See results
Now we just need to start the mlflow UI to have a look at our two pipeline runs.
To do this we need to run:

```shell
mlflow ui --backend-store-uri <SPECIFIC_MLRUNS_PATH_GOES_HERE>
```

Check the terminal output of the pipeline run to see the exact path appropriate
in your specific case. This will start mlflow at `localhost:5000`. If this port
is already in use on your machine you may have to specify another port:

```shell
 mlflow ui --backend-store-uri <SPECIFIC_MLRUNS_PATH_GOES_HERE> -p 5001
 ```

### 🧽 Clean up
In order to clean up, delete the remaining ZenML references.

```shell
rm -rf zenml_examples
rm -rf <SPECIFIC_MLRUNS_PATH_GOES_HERE>
```

# 📜 Learn more

Our docs regarding the mlflow tracking integration can be found [here](TODO: Link to docs).

If you want to learn more about visualizers in general or about how to build your own visualizers in zenml
check out our [docs](TODO: Link to docs)
