import asyncio

# Логин-шелл: подхватывает PATH из ~/.zprofile (homebrew, uv, kubectl).
# Интерактивные алиасы из ~/.zshrc недоступны — пиши полные команды.
SHELL = ["/bin/zsh", "-lc"]
MAX_OUTPUT = 8000
DEFAULT_TIMEOUT_S = 120


async def run_shell(command: str, cwd: str, timeout_s: int = DEFAULT_TIMEOUT_S) -> tuple[int, str]:
    """Выполняет команду напрямую, без агента. Возвращает (код возврата, вывод).

    stdout и stderr склеены: в чате важно видеть и ошибки тоже.
    """
    process = await asyncio.create_subprocess_exec(
        *SHELL,
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    try:
        raw, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_s)
    except (TimeoutError, asyncio.TimeoutError):
        process.kill()
        await process.wait()
        return 124, f"⏱ таймаут {timeout_s}s — команда убита"

    output = raw.decode("utf-8", errors="replace")
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + f"\n… вывод обрезан ({len(raw)} байт)"

    return process.returncode or 0, output.strip() or "(пустой вывод)"
