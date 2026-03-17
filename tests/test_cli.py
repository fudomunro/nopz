from pathlib import Path

import pytest

from nopz.cli import load_conditions


def test_load_conditions_plain_text(tmp_path: Path):
    test_file = tmp_path / "conditions.txt"
    test_file.write_text("Condition 1\n  Condition 2 \n\nCondition 3\n")

    conditions = load_conditions(str(test_file))
    assert conditions == ["Condition 1", "Condition 2", "Condition 3"]


def test_load_conditions_yaml_dict(tmp_path: Path):
    test_file = tmp_path / "conditions.yaml"
    yaml_content = """
conditions:
  - YAML condition 1
  - YAML condition 2
    """
    test_file.write_text(yaml_content)

    conditions = load_conditions(str(test_file))
    assert conditions == ["YAML condition 1", "YAML condition 2"]


def test_load_conditions_yaml_list(tmp_path: Path):
    test_file = tmp_path / "conditions.yml"
    yaml_content = """
- List condition 1
- List condition 2
    """
    test_file.write_text(yaml_content)

    conditions = load_conditions(str(test_file))
    assert conditions == ["List condition 1", "List condition 2"]


def test_load_conditions_file_not_found():
    with pytest.raises(SystemExit) as excinfo:
        load_conditions("does_not_exist.txt")
    assert excinfo.value.code == 1


def test_load_conditions_invalid_yaml(tmp_path: Path):
    test_file = tmp_path / "conditions.yaml"
    yaml_content = """
wrong_key:
  - Some condition
    """
    test_file.write_text(yaml_content)

    with pytest.raises(SystemExit) as excinfo:
        load_conditions(str(test_file))
    assert excinfo.value.code == 1
