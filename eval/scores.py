from typing import Any, Dict
import json

from opik.evaluation.metrics import base_metric
from opik.evaluation.metrics import score_result

class EqualsJSON(base_metric.BaseMetric):
    """
    A metric that checks if an output JSON exactly matches an expected output JSON.

    This metric returns a score of 1.0 if the JSONs match exactly, and 0.0 otherwise.
    The comparison can be made case-sensitive or case-insensitive for string values.

    Args:
        case_sensitive: Whether string comparison should be case-sensitive. Defaults to False.
        name: The name of the metric. Defaults to "equals_metric".
        track: Whether to track the metric. Defaults to True.

    Example:
        >>> from opik.evaluation.metrics import Equals
        >>> equals_metric = Equals(case_sensitive=True)
        >>> result = equals_metric.score('{"key": "value"}', '{"key": "value"}')
        >>> print(result.value)
        1.0
        >>> result = equals_metric.score('{"key": "Value"}', '{"key": "value"}')
        >>> print(result.value)
        0.0
    """

    def __init__(
        self,
        case_sensitive: bool = False,
        exclude_fields: list = [],
        name: str = "equals_metric",
        track: bool = True,
    ):
        super().__init__(
            name=name,
            track=track,
        )
        self._case_sensitive = case_sensitive
        # Ensure exclude_fields is a set for efficient lookup
        self._exclude_fields = set(exclude_fields or [])

    def _json_with_exclude(self, data: Any) -> Any:
        """
        Recursively remove fields listed in self._exclude_fields from a nested structure (dict or list).

        Args:
            data: The dictionary or list to process.

        Returns:
            A new dictionary or list with excluded fields removed.
        """
        if isinstance(data, dict):
            return {
                key: self._json_with_exclude(value)
                for key, value in data.items()
                if key not in self._exclude_fields
            }
        elif isinstance(data, list):
            return [self._json_with_exclude(item) for item in data]
        else:
            return data

    def score(
        self, output: Dict, expected_output: Dict, **ignored_kwargs: Any
    ) -> score_result.ScoreResult:
        """
        Calculate the score based on whether the output JSON exactly matches the expected output JSON,
        ignoring specified fields recursively.

        Args:
            output: The output dictionary to check.
            expected_output: The expected output dictionary to compare against.
            **ignored_kwargs: Additional keyword arguments that are ignored.

        Returns:
            score_result.ScoreResult: A ScoreResult object with a value of 1.0 if the processed
                dictionaries match, 0.0 otherwise.
        """
        try:
            # Recursively filter out excluded fields
            output_filtered = self._json_with_exclude(output)
            expected_filtered = self._json_with_exclude(expected_output)

            # TODO: Add case-insensitive comparison if self._case_sensitive is False
            output_json = json.dumps(output_filtered, sort_keys=True)
            reference_json = json.dumps(expected_filtered, sort_keys=True)

            if output_json == reference_json:
                return score_result.ScoreResult(value=1.0, name=self.name)

            return score_result.ScoreResult(value=0.0, name=self.name)
        except TypeError as e:
            # Handle potential issues with non-serializable types after filtering
            # Or log the error appropriately
            print(f"Error during JSON processing: {e}")
            return score_result.ScoreResult(value=0.0, name=self.name)