import os
from pathlib import Path
from unittest.mock import patch

import pytest

from nopz.cli import load_regulations, main
from nopz import regulations as reg_module
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
    output_dir = tmp_path / "output_dir"

    original_cwd = os.getcwd()

    try:
        with (
            patch("sys.argv", ["nopz", str(file_a), str(file_b), "--output", str(output_dir)]),
            patch("nopz.runner.Runner.run", return_value=True),
        ):
            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == 0
            assert output_dir.exists()
    finally:
        os.chdir(original_cwd)


def test_main_with_output(tmp_path: Path):
    test_file = tmp_path / "regs.py"
    test_file.write_text(
        'from nopz.regulations import regulation, RegulationResult\n\n'
        '@regulation("test_reg")\n'
        'def test_reg():\n'
        '    return RegulationResult(passed=True, name="test_reg")\n'
    )
    output_dir = tmp_path / "output_dir"

    original_cwd = os.getcwd()

    try:
        with (
            patch("sys.argv", ["nopz", str(test_file), "--output", str(output_dir)]),
            patch("nopz.runner.Runner.run", return_value=True),
        ):
            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == 0
            assert output_dir.exists()
            assert os.getcwd() == str(output_dir)
    finally:
        os.chdir(original_cwd)
