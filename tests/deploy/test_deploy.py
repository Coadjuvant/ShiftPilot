from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") if os.name != "nt" else r"C:\Program Files\Git\bin\bash.exe"


@pytest.fixture
def deployment(tmp_path):
    if not BASH or not Path(BASH).exists():
        pytest.skip("Bash is required for deployment tests")
    def git(*args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()
    remote, seed, server, fakebin = [tmp_path / name for name in ("remote.git", "seed", "server", "bin")]
    git("init", "--bare", "--initial-branch=main", str(remote))
    git("clone", str(remote), str(seed))
    git("config", "user.email", "test@example.invalid", cwd=seed)
    git("config", "user.name", "Deployment test", cwd=seed)
    (seed / "docker-compose.yml").write_text("services: {}\n")
    git("add", ".", cwd=seed)
    git("commit", "-m", "Initial release", cwd=seed)
    git("push", "origin", "main", cwd=seed)
    git("clone", str(remote), str(server))
    (server / "deploy-scripts").mkdir()
    (seed / "docker-compose.yml").write_text("services: {}\n# next release\n")
    git("commit", "-am", "Next release", cwd=seed)
    git("push", "origin", "main", cwd=seed)
    fakebin.mkdir()
    docker = fakebin / "docker"
    docker.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
case "$*" in
  'compose version') echo 'Docker Compose version v2.40.0';;
  'compose ps -aq backend') echo backend-container;;
  'compose ps -aq frontend') echo frontend-container;;
  inspect*) echo previous-image;;
  'compose build backend frontend') [[ "${FAIL_BUILD:-0}" != 1 ]];;
  'compose up -d --no-build --wait --wait-timeout 180') [[ "${FAIL_UP:-0}" != 1 ]];;
  'compose -f '*) cat "$5" >> "$CALLS";;
  *) exit 0;;
esac
''', encoding="utf-8", newline="\n")
    docker.chmod(0o755)
    if os.name == "nt":
        # Git Bash lacks util-linux. These scenarios test release behavior, not OS file locks.
        (fakebin / "flock").write_text("#!/usr/bin/env bash\nexit 0\n", newline="\n")
    calls = tmp_path / "calls"
    env = {**os.environ, "PATH": str(fakebin) + os.pathsep + os.environ["PATH"], "REPO_DIR": server.as_posix(),
           "LOG_FILE": (tmp_path / "deploy.log").as_posix(), "LOCK_FILE": (tmp_path / "deploy.lock").as_posix(), "CALLS": calls.as_posix()}
    def run(**overrides):
        return subprocess.run([BASH, (ROOT / "auto-deploy.sh").as_posix()], env={**env, **overrides}, capture_output=True, text=True, timeout=30)
    return run, calls, server


def test_build_failure_keeps_existing_containers(deployment):
    run, calls, server = deployment
    result = run(FAIL_BUILD="1")
    assert result.returncode != 0
    commands = calls.read_text()
    assert "compose build" in commands and "compose up" not in commands and "compose down" not in commands
    assert (server / "deploy-scripts/.local-deploy-failed").exists()
    assert run().returncode == 0  # Same commit is retried instead of skipped.


def test_unhealthy_release_rolls_back_images(deployment):
    run, calls, server = deployment
    result = run(FAIL_UP="1")
    assert result.returncode != 0
    commands = calls.read_text()
    assert "compose -f docker-compose.yml -f" in commands
    assert "/api/health" in commands  # Rollback images predate /api/ready.
    assert "compose down" not in commands
    assert (server / "deploy-scripts/.local-deploy-failed").exists()


def test_success_then_no_changes_skips_rebuild(deployment):
    run, calls, _ = deployment
    first = run()
    assert first.returncode == 0, first.stdout + first.stderr
    before = calls.read_text().count("compose build")
    assert run().returncode == 0
    assert calls.read_text().count("compose build") == before


def test_dirty_checkout_is_not_stashed_or_overwritten(deployment):
    run, calls, server = deployment
    (server / "docker-compose.yml").write_text("local edits\n")
    assert run().returncode != 0
    assert "compose build" not in calls.read_text()
    assert (server / "docker-compose.yml").read_text() == "local edits\n"
