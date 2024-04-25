import os
from datetime import datetime
from typing import Any, List, Optional, Tuple

from zenml.annotators.base_annotator import BaseAnnotator
from zenml.enums import StackComponentType
from zenml.stack.stack_component import StackComponentConfig

try:
    from pigeon import annotate
except ImportError:
    raise ImportError(
        "The 'pigeon-jupyter' package is not installed. Please install it to use the PigeonAnnotator."
    )


class PigeonAnnotatorConfig(StackComponentConfig):
    """Config for the Pigeon annotator."""

    notebook_only: bool = True
    output_dir: str


class PigeonAnnotator(BaseAnnotator):
    """Annotator for using Pigeon in Jupyter notebooks."""

    @property
    def config(self) -> PigeonAnnotatorConfig:
        return PigeonAnnotatorConfig(self._config)

    def get_url(self) -> str:
        raise NotImplementedError("Pigeon annotator does not have a URL.")

    def get_url_for_dataset(self, dataset_name: str) -> str:
        raise NotImplementedError("Pigeon annotator does not have a URL.")

    def get_datasets(self) -> List[str]:
        """Get a list of datasets (annotation files) in the output directory."""
        output_dir = self.config.output_dir
        return [f for f in os.listdir(output_dir) if f.endswith(".txt")]

    def get_dataset_names(self) -> List[str]:
        """Get a list of dataset names (annotation file names) in the output directory."""
        return self.get_datasets()

    def get_dataset_stats(self, dataset_name: str) -> Tuple[int, int]:
        """Get the number of labeled and unlabeled examples in a dataset (annotation file).

        Args:
            dataset_name: Name of the dataset (annotation file).

        Returns:
            A tuple containing (num_labeled_examples, num_unlabeled_examples).
        """
        dataset_path = os.path.join(self.config.output_dir, dataset_name)
        num_labeled_examples = sum(1 for _ in open(dataset_path))
        num_unlabeled_examples = 0  # Assuming all examples are labeled
        return num_labeled_examples, num_unlabeled_examples

    def launch(
        self,
        type: str,
        data: List[Any],
        options: List[str],
        display_fn: Optional[Any] = None,
    ) -> None:
        """Launch the Pigeon annotator in the Jupyter notebook.

        Args:
            type: Type of annotation task ('text_classification', 'image_classification', etc.).
            data: List of data items to annotate.
            options: List of options for classification tasks.
            display_fn: Optional function for displaying data items.
        """
        annotations = annotate(
            examples=data,
            options=options,
            display_fn=display_fn,
        )
        self._save_annotations(annotations)

    def add_dataset(self, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Pigeon annotator does not support adding datasets."
        )

    def delete_dataset(self, dataset_name: str) -> None:
        """Delete a dataset (annotation file).

        Args:
            dataset_name: Name of the dataset (annotation file) to delete.
        """
        dataset_path = os.path.join(self.config.output_dir, dataset_name)
        os.remove(dataset_path)

    def get_dataset(self, dataset_name: str) -> List[Tuple[Any, Any]]:
        """Get the annotated examples from a dataset (annotation file).

        Args:
            dataset_name: Name of the dataset (annotation file).

        Returns:
            A list of tuples containing (example, label) for each annotated example.
        """
        dataset_path = os.path.join(self.config.output_dir, dataset_name)
        with open(dataset_path, "r") as f:
            lines = f.readlines()
        annotations = [line.strip().split("\t") for line in lines]
        return [(example, label) for example, label in annotations]

    def get_labeled_data(self, dataset_name: str) -> List[Tuple[Any, Any]]:
        """Get the labeled examples from a dataset (annotation file).

        Args:
            dataset_name: Name of the dataset (annotation file).

        Returns:
            A list of tuples containing (example, label) for each labeled example.
        """
        return self.get_dataset(dataset_name)

    def get_unlabeled_data(self, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "Pigeon annotator does not support retrieving unlabeled data."
        )

    def _save_annotations(self, annotations: List[Any]) -> None:
        """Save annotations to a file with a unique date-time suffix.

        Args:
            annotations: List of annotated examples.
        """
        output_dir = self.config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"annotations_{timestamp}.txt")
        with open(output_file, "w") as f:
            for example, label in annotations:
                f.write(f"{example}\t{label}\n")


class PigeonAnnotatorFlavor(StackComponentFlavor):
    """Pigeon annotator flavor."""

    @property
    def type(self) -> StackComponentType:
        return StackComponentType.ANNOTATOR

    @property
    def config_class(self) -> Type[PigeonAnnotatorConfig]:
        return PigeonAnnotatorConfig

    @property
    def implementation_class(self) -> Type[PigeonAnnotator]:
        return PigeonAnnotator
