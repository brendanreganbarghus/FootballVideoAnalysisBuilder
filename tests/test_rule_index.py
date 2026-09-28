import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "generate_rule_index", PROJECT_ROOT / "scripts" / "generate-rule-index.py"
)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def test_every_rule_test_has_a_timestamp_suffix() -> None:
    rules, unstamped = generator.collect_rule_tests()

    assert rules
    assert unstamped == []
    stamps = [item["stamp"] for item in rules]
    assert len(stamps) == len(set(stamps)), "rule timestamps must be unique"


def test_rule_index_is_current() -> None:
    rules, _ = generator.collect_rule_tests()

    assert generator.INDEX_PATH.read_text(encoding="utf-8") == (
        generator.render_index(rules)
    ), "run: python scripts/generate-rule-index.py"
