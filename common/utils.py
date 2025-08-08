def extract_json(response: str) -> str:
    """
    Extracts the JSON from the response using stack-based parsing to match braces.
    """
    # First try to extract from markdown code blocks
    try:
        if "```json" in response:
            return response.split("```json")[1].split("```")[0]
    except IndexError:
        pass
    
    # Find the first opening brace
    start_idx = response.find("{")
    if start_idx == -1:
        # No JSON found, return original response
        return response
    
    # Use stack-based parsing to find matching closing brace
    stack = []
    for i, char in enumerate(response[start_idx:], start_idx):
        if char == "{":
            stack.append(char)
        elif char == "}":
            if stack:
                stack.pop()
                if not stack:
                    # Found matching closing brace
                    return response[start_idx:i+1]
    
    # If we get here, unmatched braces - return from start to end
    return response[start_idx:]
