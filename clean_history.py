import json
import argparse


def clean_history_file(filepath: str) -> None:
    """
    Read a JSON file, recursively remove all 'screenshot' keys, and write back to the same file.
    
    Args:
        filepath: Path to the JSON file to clean
    """
    # Read the JSON file
    with open(filepath, "r") as f:
        data = json.load(f)
    
    def remove_screenshots(obj):
        """Recursively remove 'screenshot' keys from a dict/list structure"""
        if isinstance(obj, dict):
            # Create new dict without screenshot key
            return {
                k: remove_screenshots(v) 
                for k, v in obj.items()
                if k != "screenshot"
            }
        elif isinstance(obj, list):
            return [remove_screenshots(item) for item in obj]
        else:
            return obj

    # Clean the data
    cleaned_data = remove_screenshots(data)

    # Write back to same file
    with open(filepath, "w") as f:
        json.dump(cleaned_data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Clean screenshot data from JSON history files")
    parser.add_argument("filepath", help="Path to the JSON file to clean")
    args = parser.parse_args()
    
    clean_history_file(args.filepath)


if __name__ == "__main__":
    main()

