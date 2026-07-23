from tgclaude.render import chunks, progress_text, to_html


def test_progress_lists_steps_while_running():
    out = progress_text(["Bash: git status", "Read: main.go"])

    assert out.startswith("⏳")
    assert "▸ Bash: git status" in out
    assert "▸ Read: main.go" in out


def test_progress_collapses_when_finished():
    out = progress_text(["a", "b", "c"], finished=True, elapsed_s=47.4, status="ok")

    assert out == "✅ 3 шага, 47s"


def test_progress_shows_interrupted_status():
    assert progress_text(["a"], finished=True, elapsed_s=2.0, status="stopped") == "⛔ прервано, 1 шаг, 2s"


def test_progress_shows_error_status():
    assert progress_text([], finished=True, elapsed_s=1.0, status="error") == "❌ ошибка, 0 шагов, 1s"


def test_progress_keeps_only_last_steps_when_long():
    out = progress_text([f"step {i}" for i in range(50)])

    assert "step 49" in out
    assert "step 0" not in out
    assert len(out) < 4096


def test_to_html_escapes_special_characters():
    assert to_html("a < b & c") == "a &lt; b &amp; c"


def test_to_html_converts_fenced_code_block():
    out = to_html("before\n```\nls -la\n```\nafter")

    assert "<pre>ls -la</pre>" in out
    assert "before" in out and "after" in out


def test_to_html_converts_inline_code():
    assert to_html("run `make test` now") == "run <code>make test</code> now"


def test_to_html_escapes_inside_code_block():
    assert "<pre>a &lt; b</pre>" in to_html("```\na < b\n```")


def test_chunks_returns_single_piece_when_short():
    assert chunks("hello") == ["hello"]


def test_chunks_splits_on_newline_boundary():
    text = "\n".join(["x" * 100] * 60)

    parts = chunks(text, limit=1000)

    assert len(parts) > 1
    assert all(len(p) <= 1000 for p in parts)
    # Each boundary consumes exactly one separator newline; re-inserting one
    # newline per boundary must reconstruct the original with no lost chars.
    assert "\n".join(parts) == text


def test_chunks_hard_splits_when_no_newline():
    parts = chunks("y" * 2500, limit=1000)

    assert [len(p) for p in parts] == [1000, 1000, 500]


def test_chunks_preserves_blank_line_at_boundary():
    text = "A" * 990 + "\n\n" + "B" * 500

    parts = chunks(text, limit=992)

    assert "".join(parts).count("A") == 990
    assert "".join(parts).count("B") == 500
    # The blank line's newlines must survive (only one consumed as separator).
    assert "\n".join(parts) == text


def test_to_html_strips_nul_and_avoids_placeholder_collision():
    out = to_html("marker \x000\x00 x ```\ncode\n```")

    assert out.count("<pre>code</pre>") == 1
    assert "\x00" not in out
