from urllib.parse import urlparse

def _is_in_scope(url: str, scopes: list[str]) -> bool:
    """Return True if scopes are empty or the URL starts with any configured scope prefix."""
    if not scopes:
        return True
            
    parsed_url = urlparse(url)

    for scope in scopes:
        # If scope doesn't have scheme, add // to make it parse correctly
        if '://' not in scope:
            scope = '//' + scope
            
        parsed_scope = urlparse(scope)
        
        # Check host match
        if parsed_url.netloc != parsed_scope.netloc:
            continue
            
        # Check path is a subpath
        if parsed_url.path.startswith(parsed_scope.path):
            return True
            
    return False

# Test examples
def test_is_in_scope():
    # Test empty scopes - should return True for any URL
    assert _is_in_scope("https://example.com/path", []) == True
    assert _is_in_scope("http://test.org/api", []) == True
    
    # Test exact host and path match
    scopes = ["example.com/api"]
    assert _is_in_scope("https://example.com/api", scopes) == True
    assert _is_in_scope("https://example.com/api/users", scopes) == True
    assert _is_in_scope("https://example.com/api/users/123", scopes) == True

test_is_in_scope()