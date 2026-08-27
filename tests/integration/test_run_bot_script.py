"""Behavior checks for the local bot launcher."""

import shutil
import stat
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_SCRIPT = PROJECT_ROOT / "run_bot.sh"


def test_run_script_starts_module_from_project_root_when_called_elsewhere(
    tmp_path: Path,
) -> None:
    assert RUN_SCRIPT.exists(), "run_bot.sh loyiha root'ida mavjud bo‘lishi kerak"

    fake_project = tmp_path / "project"
    fake_python = fake_project / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text(
        "#!/bin/sh\nprintf 'cwd=%s\\n' \"$PWD\"\nprintf 'args=%s\\n' \"$*\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
    (fake_project / ".env").touch()
    copied_script = Path(shutil.copy2(RUN_SCRIPT, fake_project / RUN_SCRIPT.name))

    result = subprocess.run(
        [str(copied_script)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        f"cwd={fake_project}",
        "args=-m namoz_bot.main",
    ]


def test_run_script_reports_missing_env_file(tmp_path: Path) -> None:
    fake_project = tmp_path / "project"
    fake_python = fake_project / ".venv" / "bin" / "python"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
    copied_script = Path(shutil.copy2(RUN_SCRIPT, fake_project / RUN_SCRIPT.name))

    result = subprocess.run(
        [str(copied_script)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 1
    assert result.stderr == f"Xato: {fake_project}/.env topilmadi.\n"


def test_run_script_reports_missing_virtual_environment(tmp_path: Path) -> None:
    fake_project = tmp_path / "project"
    fake_project.mkdir()
    (fake_project / ".env").touch()
    copied_script = Path(shutil.copy2(RUN_SCRIPT, fake_project / RUN_SCRIPT.name))

    result = subprocess.run(
        [str(copied_script)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    expected_python = fake_project / ".venv" / "bin" / "python"
    assert result.returncode == 1
    assert result.stderr == (f"Xato: {expected_python} topilmadi. Avval virtual muhit yarating.\n")
