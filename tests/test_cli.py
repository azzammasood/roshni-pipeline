from typer.testing import CliRunner

from roshni import __version__
from roshni.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_info() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "data-sources" in result.stdout
