"""Bare owner/repo detection must not hijack ordinary questions.
Run from the project root: .venv/bin/python backend/test_classifier_github_detection.py"""
from backend.verification.classifier import classify_query

KESTREL = (
    "System/Instruction: Answer using ONLY the facts in the Context below. Do not infer, "
    'extrapolate, or use outside knowledge. If a detail is not explicitly stated in the Context, '
    'reply with "Not specified in context."\n\nContext:\nProject Kestrel (v2.4.1) runs on an '
    "STM32H743 microcontroller. Sensor telemetry is sampled at 250 Hz over SPI2 and sent over UART3.\n\n"
    "Questions:\n1. Which DMA stream is used?\n2. What is the clock frequency of the SPI2 peripheral?"
)

NOT_GITHUB = [
    KESTREL,
    "what is 3/4 of 120?",
    "is it and/or logic?",
    "explain TCP/IP and I/O ports",
    "what does src/utils do in my project",
    "the meeting is on 12/05",
]

IS_GITHUB = [
    "what does Mosope16/pulse_watch do?",
    "Tell me about Mosope16/pulse_watch",
    "What does testuser/bare_repo do?",
    "tell me about torvalds/linux on github",
    "Mosope16/pulse_watch",
    "Please inspect https://github.com/Mosope16/moso-ai and explain it.",
]

def run():
    for q in NOT_GITHUB:
        i = classify_query(q)
        assert i.task_type != "github_inspect", f"false positive: {q[:50]!r} -> {i.entities}"
    for q in IS_GITHUB:
        i = classify_query(q)
        assert i.task_type == "github_inspect", f"missed repo: {q[:50]!r} -> {i.task_type}"
    print(f"PASS {len(NOT_GITHUB)} non-repo and {len(IS_GITHUB)} repo cases")

def run_gate():
    """The evidence gate must not abstain on prompts that were never about GitHub."""
    from backend.verification.evidence_gating import EvidenceRegistry, evaluate_evidence_gating
    for q in NOT_GITHUB:
        d = evaluate_evidence_gating(classify_query(q), q, EvidenceRegistry())
        assert not d.requires_abstention, f"gate abstained on non-repo prompt: {q[:50]!r}"
    for q in IS_GITHUB:
        d = evaluate_evidence_gating(classify_query(q), q, EvidenceRegistry())
        assert d.requires_abstention, f"gate should abstain when a repo was named but never fetched: {q[:50]!r}"
    print(f"PASS gate: {len(NOT_GITHUB)} non-repo prompts proceed, {len(IS_GITHUB)} repo prompts still gated")


if __name__ == "__main__":
    run()
    run_gate()
