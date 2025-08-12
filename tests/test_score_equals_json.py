import unittest
import sys
from pathlib import Path

# Add the parent directory to sys.path to find the eval module
sys.path.append(str(Path(__file__).resolve().parent.parent))

from eval.scores import EqualsJSON

class TestEqualsJSON(unittest.TestCase):

    def test_empty_list_values(self):
        """
        Test that comparing two dictionaries with empty lists as values results in a score of 1.0.
        """
        metric = EqualsJSON(exclude_fields=["description"])
        output = {"resources": [], "description": "test"}
        expected_output = {"resources": []}
        result = metric.score(output, expected_output)
        self.assertEqual(result.value, 1.0)

if __name__ == "__main__":
    unittest.main()
