from src.tools.finding_id import finding_id


def base(**kw):
    args = dict(tool="semgrep", rule="r", file="a.py", snippet="db.execute(q)")
    return finding_id(**{**args, **kw})


def test_same_input_same_id():
    assert base() == base()


def test_whitespace_changes_do_not_change_id():
    assert base(snippet="x = a + b") == base(snippet="  x  =\n    a +   b \n")


def test_different_snippet_rule_file_or_tool_changes_id():
    ids = {base(), base(snippet="db.run(q)"), base(rule="r2"), base(file="b.py"), base(tool="trivy")}
    assert len(ids) == 5


def test_line_number_is_not_part_of_the_id():
    # The signature has no line argument at all: moving code must not change its identity.
    assert "line" not in finding_id.__code__.co_varnames
