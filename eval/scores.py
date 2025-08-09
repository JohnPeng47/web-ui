import json
from typing import Any, Dict, List, Set, Optional

from opik.evaluation.metrics import BaseMetric
from opik.evaluation.metrics import score_result

class EqualsJSON(BaseMetric):
    """       
    Evaluator that checks if the output JSON matches the expected JSON exactly,
    allowing for specific fields to be excluded and optionally ignoring case
    or only considering keys present in the expected output.
    """

    def __init__(
        self,
        exclude_fields: Optional[List[str]] = None,
        case_sensitive: bool = True,
        only_expected_keys: bool = False,
    ):
        """
        Initialize the scorer.

        Args:
            exclude_fields (Optional[List[str]]): A list of field names (keys) to exclude
                from the comparison at any level of the JSON structure. Defaults to None.
            case_sensitive (bool): Whether the comparison should be case-sensitive.
                Defaults to True. TODO: Implement case-insensitive comparison.
            only_expected_keys (bool): If True, only compare keys present in the
                expected output. Keys present in the output but not in the expected
                output will be ignored. Defaults to False.
            name (Optional[str]): The name of the scorer. Defaults to "JSON Exact Match".
        """
        self._exclude_fields: Set[str] = set(exclude_fields) if exclude_fields else set()
        self._case_sensitive = case_sensitive # TODO: Implement case-insensitive logic
        self._only_expected_keys = only_expected_keys
        self.name = "JSON_exact_match" if not only_expected_keys else "JSON_only_expected_keys"

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

    def _filter_by_expected_keys(self, output_data: Any, expected_data: Any) -> Any:
        """
        Recursively filter output_data to only include keys present in expected_data.
        This filtering only applies when both output_data and expected_data are dictionaries
        at the current level.

        Args:
            output_data: The data structure to filter (derived from the output).
            expected_data: The data structure providing the reference keys (derived from expected).

        Returns:
            A new data structure based on output_data, containing only keys also in expected_data.
        """
        if isinstance(expected_data, dict) and isinstance(output_data, dict):
            result_dict = {}
            for key, expected_value in expected_data.items():
                if key in output_data:
                    result_dict[key] = self._filter_by_expected_keys(output_data[key], expected_value)
            return result_dict
        elif isinstance(expected_data, list) and isinstance(output_data, list):
            # For lists, we assume the structure should align. Filter element-wise.
            # Note: This assumes lists are of the same length for meaningful filtering.
            # If lengths differ, the final string comparison will likely catch it.
             return [
                self._filter_by_expected_keys(out_item, exp_item)
                for out_item, exp_item in zip(output_data, expected_data)
            ]
        else:
            # If expected is not a dict/list, or types mismatch, return output_data as is.
            # The final comparison will determine the match.
            return output_data

    def score(
        self, output: Dict, expected_output: Dict | List | str, **ignored_kwargs: Any
    ) -> score_result.ScoreResult:
        """
        Calculate the score based on whether the output JSON matches the expected output JSON,
        applying configured filtering options.

        Args:
            output: The output dictionary to check.
            expected_output: The expected output dictionary to compare against.
            **ignored_kwargs: Additional keyword arguments that are ignored.

        Returns:
            score_result.ScoreResult: A ScoreResult object with a value of 1.0 if the processed
                dictionaries match, 0.0 otherwise.
        """
        try:
            if isinstance(expected_output, str):
                try:
                    expected_output = json.loads(expected_output)
                except json.JSONDecodeError:
                     print(f"Error: expected_output is not valid JSON: {expected_output}")
                     return score_result.ScoreResult(value=0.0, name=self.name)

            if not isinstance(output, (dict, list)):
                 print(f"Error: output is not a dict or list: {output}")
                 # Attempt to parse if it's a string representation
                 if isinstance(output, str):
                    try:
                        output = json.loads(output)
                    except json.JSONDecodeError:
                         print(f"Error: output string is not valid JSON: {output}")
                         return score_result.ScoreResult(value=0.0, name=self.name)
                 else:
                    return score_result.ScoreResult(value=0.0, name=self.name)

            # 1. Recursively filter out globally excluded fields
            output_filtered_excluded = self._json_with_exclude(output)
            expected_filtered_excluded = self._json_with_exclude(expected_output)

            # 2. Optionally filter output to only include keys present in expected
            if self._only_expected_keys:
                 output_final = self._filter_by_expected_keys(output_filtered_excluded, expected_filtered_excluded)
                 expected_final = expected_filtered_excluded # Expected remains the reference
            else:
                 output_final = output_filtered_excluded
                 expected_final = expected_filtered_excluded


            # TODO: Add case-insensitive comparison if self._case_sensitive is False
            # 3. Compare the final processed structures
            output_json = json.dumps(output_final, sort_keys=True)
            reference_json = json.dumps(expected_final, sort_keys=True)


            if output_json == reference_json:
                # If the JSONs match, return a score of 1.0
                return score_result.ScoreResult(value=1.0, name=self.name)

            # If they don't match return 0.0
            return score_result.ScoreResult(value=0.0, name=self.name)
        except TypeError as e:
            # Handle potential issues with non-serializable types after filtering
            # Or log the error appropriately
            print(f"Error during JSON processing: {e}")
            return score_result.ScoreResult(value=0.0, name=self.name)
        except Exception as e: # Catch other potential errors
            print(f"An unexpected error occurred during scoring: {e}")
            return score_result.ScoreResult(value=0.0, name=self.name)