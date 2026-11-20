"""Tests for fit_messages_to_budget (no third-party deps). Run: python backend/test_context_fit.py"""
import importlib.util, pathlib

_spec = importlib.util.spec_from_file_location(
    "context_manager", pathlib.Path(__file__).parent / "verification" / "context_manager.py"
)
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

EVIDENCE = "word " * 6000  # ~30k chars, far over a 4096 window
TOOL = (
    "### VERIFIED RETRIEVED EVIDENCE from [x](https://example.com):\n"
    "```\n" + EVIDENCE + "\n```\n\n"
    "STRICT GROUNDING INSTRUCTIONS:\n- Ground your response strictly in the verified text above."
)


def base():
    return [
        {"role": "system", "content": "You are Moso AI."},
        {"role": "user", "content": "What does this page say?"},
        {"role": "tool", "tool_name": "web_fetch", "content": TOOL},
        {"role": "system", "content": "GROUNDING DIRECTIVES: answer only from the evidence."},
    ]


def test_no_trim_when_small():
    msgs = [{"role": "system", "content": "hi"}, {"role": "user", "content": "yo"}]
    out, rep = cm.fit_messages_to_budget(msgs, 4096, 512)
    assert out == msgs and not rep["trimmed"] and not rep["over_budget"]


def test_trims_tool_and_keeps_everything_else():
    orig = base()
    out, rep = cm.fit_messages_to_budget(orig, 4096, 512)
    assert rep["trimmed"] and not rep["over_budget"], rep
    assert rep["tokens_after"] <= rep["budget"]
    assert out[0] == orig[0] and out[1] == orig[1] and out[3] == orig[3]
    assert "STRICT GROUNDING INSTRUCTIONS" in out[2]["content"]  # instructions survive the trim
    assert "evidence trimmed" in out[2]["content"]
    assert orig[2]["content"] == TOOL  # input not mutated


def test_over_budget_flag_when_nothing_left_to_trim():
    msgs = [{"role": "system", "content": "x" * 20000}, {"role": "user", "content": "q"}]
    out, rep = cm.fit_messages_to_budget(msgs, 4096, 512)
    assert rep["over_budget"] and not rep["trimmed"]


def test_larger_window_needs_less_trimming():
    _, small = cm.fit_messages_to_budget(base(), 4096, 512)
    _, big = cm.fit_messages_to_budget(base(), 8192, 512)
    assert big["tokens_after"] > small["tokens_after"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)}/{len(tests)} passed")
