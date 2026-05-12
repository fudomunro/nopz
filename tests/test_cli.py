import os
from pathlib import Path
from unittest.mock import patch

import pytest

from nopz.cli import load_regulations, main
from nopz.regulations import RegulationResult, regulation, get_regulations


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
