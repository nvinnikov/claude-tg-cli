from pathlib import Path

from tgclaude.shell import MAX_OUTPUT, run_shell


async def test_returns_stdout_and_zero_code(tmp_path: Path):
    code, out = await run_shell("echo hello", cwd=str(tmp_path), timeout_s=10)

    assert code == 0
    assert out.strip() == "hello"


async def test_captures_stderr_together_with_stdout(tmp_path: Path):
    code, out = await run_shell("echo oops 1>&2", cwd=str(tmp_path), timeout_s=10)

    assert code == 0
    assert "oops" in out


async def test_returns_nonzero_exit_code(tmp_path: Path):
    code, _ = await run_shell("exit 3", cwd=str(tmp_path), timeout_s=10)

    assert code == 3


async def test_runs_in_given_cwd(tmp_path: Path):
    (tmp_path / "marker.txt").write_text("x")

    _, out = await run_shell("ls", cwd=str(tmp_path), timeout_s=10)

    assert "marker.txt" in out


async def test_timeout_kills_command(tmp_path: Path):
    code, out = await run_shell("sleep 5", cwd=str(tmp_path), timeout_s=1)

    assert code != 0
    assert "таймаут" in out.lower()


async def test_long_output_is_truncated(tmp_path: Path):
    code, out = await run_shell(
        f"python3 -c \"print('x' * {MAX_OUTPUT * 2})\"", cwd=str(tmp_path), timeout_s=30
    )

    assert code == 0
    assert len(out) <= MAX_OUTPUT + 200
    assert "обрезан" in out


async def test_empty_output_is_reported(tmp_path: Path):
    code, out = await run_shell("true", cwd=str(tmp_path), timeout_s=10)

    assert code == 0
    assert out == "(пустой вывод)"
