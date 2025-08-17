from src.agent.discovery.prompts.planv4 import PlanItem


def _build_tree_a() -> PlanItem:
    root = PlanItem(description="ROOT")

    login = root.add_to_root("Login")
    login._add_child("Enter username")
    login._add_child("Enter password")

    root._add_child("Click submit")

    profile = root._add_child("Profile")
    profile._add_child("Update bio")

    return root


def _build_tree_b() -> PlanItem:
    root = PlanItem(description="ROOT")

    login = root.add_to_root("Login")
    login._add_child("Enter username")
    login._add_child("Enter password")
    login._add_child("Click 2FA")  # new leaf under existing parent

    root._add_child("Go to settings")  # new top-level leaf

    security = root._add_child("Security")  # new subtree
    security._add_child("Enable 2FA")

    return root


def test_diff_no_changes_returns_empty_list():
    a = PlanItem(description="ROOT")
    a.add_to_root("Only item")

    b = PlanItem(description="ROOT")
    b.add_to_root("Only item")

    assert a.diff(b) == []


def test_diff_reports_top_level_changes_only():
    a = _build_tree_a()
    b = _build_tree_b()

    print(a)
    print(b)

    diff = a.diff(b)

    got = {(item.description, op) for item, op in diff}

    expected = {
        ("Click 2FA", "+"),      # added leaf under existing parent
        ("Go to settings", "+"),  # added top-level leaf
        ("Security", "+"),        # added subtree reported only at root of subtree
        ("Profile", "-"),          # deleted subtree reported only at root of subtree
        ("Click submit", "-"),     # deleted top-level leaf
    }

    assert got == expected

