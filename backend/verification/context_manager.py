"""
Moso AI — Token-Aware Context Manager
Maintains conversation history and context within Qwen 3.5 2B's 4096-token context window:
- Estimates token consumption.
- Prioritizes recent conversation turns and active query over distant history.
- Truncates or summarizes older conversation turns when context budget is exceeded.
- Reserves at least 1,024 tokens for model generation and reasoning.
"""

from typing import List, Dict, Any, Tuple


def estimate_tokens(text: str, chars_per_token: float = 3.5) -> int:
    """Fast approximation of token count for Qwen 3.5."""
    if not text:
        return 0
    # Average across English, code, and math: ~3.5 characters per token
    return max(1, int(len(text) / chars_per_token))


class ContextManager:
    def __init__(self, max_context_tokens: int = 4096, reserved_generation_tokens: int = 1024):
        self.max_context_tokens = max_context_tokens
        self.reserved_generation_tokens = reserved_generation_tokens
        # Maximum tokens available for input (system prompt + documents + history)
        self.max_input_budget = max_context_tokens - reserved_generation_tokens  # ~3072 tokens

    def prepare_messages_for_inference(
        self,
        system_prompt: str,
        raw_messages: List[Dict[str, str]],
        document_context: str = "",
        tool_context: str = "",
    ) -> List[Dict[str, str]]:
        """
        Constructs a context-budgeted list of messages for Ollama.
        """
        # 1. System message tokens
        sys_tokens = estimate_tokens(system_prompt)

        # 2. Document & Tool context tokens (cap document context at 900 tokens)
        doc_tokens = estimate_tokens(document_context)
        tool_tokens = estimate_tokens(tool_context)
        
        # 3. Available tokens for conversation history
        remaining_history_budget = self.max_input_budget - sys_tokens - doc_tokens - tool_tokens
        if remaining_history_budget < 600:
            remaining_history_budget = 600

        # 4. Filter and budget conversation messages
        # Always preserve the latest user message
        if not raw_messages:
            return [{"role": "system", "content": system_prompt}]

        latest_msg = raw_messages[-1]
        history_msgs = raw_messages[:-1]

        budgeted_history: List[Dict[str, str]] = []
        accumulated_tokens = estimate_tokens(latest_msg.get("content", ""))

        # Walk backwards through history to keep the most recent turns
        dropped_turns_count = 0
        for msg in reversed(history_msgs):
            msg_tokens = estimate_tokens(msg.get("content", ""))
            if accumulated_tokens + msg_tokens <= remaining_history_budget:
                budgeted_history.insert(0, msg)
                accumulated_tokens += msg_tokens
            else:
                dropped_turns_count += 1

        # If older messages were dropped, insert a brief anchor summary if helpful
        final_history = []
        if dropped_turns_count > 0:
            final_history.append({
                "role": "system",
                "content": f"[System note: {dropped_turns_count} earlier turn(s) were truncated to preserve context window.]"
            })
        final_history.extend(budgeted_history)
        final_history.append(latest_msg)

        # Build full prompt
        system_content_parts = [system_prompt]
        if tool_context:
            system_content_parts.append(tool_context)
        if document_context:
            system_content_parts.append(document_context)

        combined_system = "\n\n".join(system_content_parts).strip()

        return [{"role": "system", "content": combined_system}] + final_history



# ---------------------------------------------------------------------------
# Final-prompt budget guard
#
# prepare_messages_for_inference() budgets the system prompt, history and docs,
# but web/GitHub tool results are appended to the message list afterwards.
# A single fetched page can be thousands of tokens, and Ollama silently drops
# the start of an over-long prompt (often the rules and the evidence).
# This runs right before every Ollama call and trims tool messages to fit.
# ---------------------------------------------------------------------------

_MSG_OVERHEAD_TOKENS = 6  # rough per-message chat-template overhead
_TRIM_MARKER = "\n[... evidence trimmed to fit the context window ...]\n"


def _shrink_tool_content(content: str, target_chars: int) -> str:
    """Shrink a tool message but keep the grounding instructions around the evidence.

    EvidenceContract.format_for_model() wraps the evidence in a ``` fence and puts
    the strict-grounding instructions after it, so we cut inside the fence.
    """
    if len(content) <= target_chars:
        return content
    start = content.find("```\n")
    end = content.rfind("\n```")
    if start != -1 and end > start + 4:
        head = content[: start + 4]
        tail = content[end:]
        inner_budget = target_chars - len(head) - len(tail) - len(_TRIM_MARKER)
        if inner_budget > 200:
            inner = content[start + 4 : end]
            return head + inner[:inner_budget] + _TRIM_MARKER + tail
    return content[: max(target_chars - len(_TRIM_MARKER), 200)] + _TRIM_MARKER


def fit_messages_to_budget(
    messages: List[Dict[str, Any]],
    num_ctx: int,
    num_predict: int,
    safety_tokens: int = 150,
    chars_per_token: float = 3.0,
    min_tool_tokens: int = 250,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return (messages_that_fit, report). Only role == "tool" messages are trimmed.

    Uses a conservative 3.0 chars/token because URLs, code and non-English text
    tokenize worse than plain English. The input list is not modified.
    """
    budget = num_ctx - num_predict - safety_tokens
    msgs = [dict(m) for m in messages]

    def msg_tokens(m: Dict[str, Any]) -> int:
        return estimate_tokens(m.get("content") or "", chars_per_token) + _MSG_OVERHEAD_TOKENS

    def total() -> int:
        return sum(msg_tokens(m) for m in msgs)

    before = total()
    report: Dict[str, Any] = {
        "budget": budget,
        "tokens_before": before,
        "tokens_after": before,
        "trimmed": False,
        "over_budget": False,
    }
    if before <= budget:
        return msgs, report

    tool_idx = [i for i, m in enumerate(msgs) if m.get("role") == "tool"]
    while total() > budget:
        candidates = [i for i in tool_idx if msg_tokens(msgs[i]) > min_tool_tokens + _MSG_OVERHEAD_TOKENS]
        if not candidates:
            break
        i = max(candidates, key=lambda j: len(msgs[j].get("content") or ""))
        content = msgs[i].get("content") or ""
        excess = total() - budget
        new_tokens = max(min_tool_tokens, estimate_tokens(content, chars_per_token) - excess)
        new_content = _shrink_tool_content(content, int(new_tokens * chars_per_token))
        if len(new_content) >= len(content):
            break  # no progress possible
        msgs[i]["content"] = new_content
        report["trimmed"] = True

    report["tokens_after"] = total()
    report["over_budget"] = report["tokens_after"] > budget
    return msgs, report
