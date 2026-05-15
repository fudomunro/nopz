from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from nopz.cli import load_regulations, main
from nopz import regulations as reg_module
from nopz.number_one import ReviewResult
from nopz.regulations import RegulationResult, regulation, get_regulations


@pytest.fixture(autouse=True)
def _clear_registry():
    """Clear the global regulation registry before each test."""
    reg_module._registry.clear()
    yield
    reg_module._registry.clear()


def test_load_regulations(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("test_reg", description="A test regulation")\n'
        'def test_reg():\n'
        '    return RegulationResult(passed=True, name="test_reg")\n'
    )

    regulations = load_regulations(str(test_file))
    assert len(regulations) == 1
    assert regulations[0].name == "test_reg"
    assert regulations[0].description == "A test regulation"


def test_load_regulations_file_not_found():
    with pytest.raises(SystemExit) as excinfo:
        load_regulations("does_not_exist.py")
    assert excinfo.value.code == 1


def test_regulation_decorator():
    @regulation("my_reg", description="test")
    def my_reg():
        return RegulationResult(passed=True, name="my_reg")

    assert my_reg.name == "my_reg"
    assert my_reg.description == "test"
    assert callable(my_reg.check)


def test_load_regulations_multiple_files(tmp_path: Path):
    file_a = tmp_path / "regs_a.py"
    file_a.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("reg_a")\n'
        'def reg_a():\n'
        '    return RegulationResult(passed=True, name="reg_a")\n'
    )
    file_b = tmp_path / "regs_b.py"
    file_b.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("reg_b")\n'
        'def reg_b():\n'
        '    return RegulationResult(passed=True, name="reg_b")\n'
    )

    regulations = load_regulations(str(file_a))
    regulations.extend(load_regulations(str(file_b)))
    assert len(regulations) == 2
    names = {r.name for r in regulations}
    assert names == {"reg_a", "reg_b"}


def test_main_with_multiple_files(tmp_path: Path):
    file_a = tmp_path / "regs_a.py"
    file_a.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("reg_a")\n'
        'def reg_a():\n'
        '    return RegulationResult(passed=True, name="reg_a")\n'
    )
    file_b = tmp_path / "regs_b.py"
    file_b.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("reg_b")\n'
        'def reg_b():\n'
        '    return RegulationResult(passed=True, name="reg_b")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(file_a), str(file_b), "--skip-review"]),
        patch("nopz.runner.Runner.run", return_value=True),
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 0


def test_main_with_output(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("test_reg")\n'
        'def test_reg():\n'
        '    return RegulationResult(passed=True, name="test_reg")\n'
    )
    output_dir = tmp_path / "output_dir"

    with (
        patch("sys.argv", ["nopz", str(test_file), "--output", str(output_dir), "--skip-review"]),
        patch("nopz.runner.Runner.run", return_value=True),
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 0


def test_main_no_regulations_exits(tmp_path: Path):
    test_file = tmp_path / "empty.py"
    test_file.write_text("# no regulations here\n")

    with (
        patch("sys.argv", ["nopz", str(test_file)]),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 1


def test_main_keyboard_interrupt(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(test_file), "--skip-review"]),
        patch("nopz.runner.Runner.run", side_effect=KeyboardInterrupt),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 130


def test_main_generic_exception(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(test_file), "--skip-review"]),
        patch("nopz.runner.Runner.run", side_effect=RuntimeError("boom")),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 1


def test_main_list_models(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    mock_model = MagicMock()
    mock_model.model_id = "test-model-1"

    with (
        patch("sys.argv", ["nopz", str(test_file), "--list-models"]),
        patch("llm.get_models", return_value=[mock_model]),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 0


def test_main_debug_flag(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(test_file), "--debug", "--skip-review"]),
        patch("nopz.runner.Runner.run", return_value=True),
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0


# --- Number One Point Zero review integration tests ---


def _review_pass_results(*args, **kwargs):
    """Helper: mock NumberOne.review returning all-pass results."""
    return [ReviewResult(passed=True, regulation_name="r")]


def test_main_skip_review(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(test_file), "--skip-review"]),
        patch("nopz.runner.Runner.run", return_value=True) as mock_run,
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        mock_run.assert_called_once()


def test_main_review_passes_continues(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(test_file)]),
        patch("nopz.number_one.NumberOne.review", side_effect=_review_pass_results),
        patch("nopz.runner.Runner.run", return_value=True) as mock_run,
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        mock_run.assert_called_once()


def test_main_review_fails_exits(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    fail_results = [ReviewResult(passed=False, regulation_name="r", issues=["too vague"])]

    with (
        patch("sys.argv", ["nopz", str(test_file)]),
        patch("nopz.number_one.NumberOne.review", return_value=fail_results),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 1


def test_main_nopz_model_flag(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(test_file), "--nopz-model", "gemini-2.5-flash"]),
        patch("nopz.number_one.NumberOne.__init__", return_value=None) as mock_init,
        patch("nopz.number_one.NumberOne.review", side_effect=_review_pass_results),
        patch("nopz.number_one.NumberOne.all_passed", return_value=True),
        patch("nopz.runner.Runner.run", return_value=True),
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0
        _, kwargs = mock_init.call_args
        assert kwargs["model_name"] == "gemini-2.5-flash"


def test_main_guidelines_flag(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )
    guidelines_file = tmp_path / "custom.yaml"
    guidelines_file.write_text(
        yaml.dump({"guidelines": [{"id": "test", "name": "Test", "description": "A test"}]})
    )

    with (
        patch("sys.argv", ["nopz", str(test_file), "--guidelines", str(guidelines_file)]),
        patch("nopz.number_one.NumberOne.review", side_effect=_review_pass_results),
        patch("nopz.runner.Runner.run", return_value=True),
    ):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 0


def test_main_guidelines_missing_file_exits(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("r")\n'
        'def r():\n'
        '    return RegulationResult(passed=True, name="r")\n'
    )

    with (
        patch("sys.argv", ["nopz", str(test_file), "--guidelines", "/nonexistent.yaml"]),
        pytest.raises(SystemExit) as excinfo,
    ):
        main()
    assert excinfo.value.code == 1
