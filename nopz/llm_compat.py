"""Monkey-patches for llm library compatibility with non-standard APIs."""

import logging

logger = logging.getLogger(__name__)

_patched = False


def patch_reasoning_content():
    """Patch llm library to preserve reasoning_content from thinking models.

    MiMo and similar thinking models return reasoning_content in streaming deltas.
    The llm library doesn't handle this field natively, so we patch combine_chunks
    to capture it and build_messages to inject it back into conversation history.
    """
    global _patched
    if _patched:
        return
    _patched = True

    try:
        from llm.default_plugins import openai_models
    except ImportError:
        logger.debug("Could not import openai_models plugin, skipping reasoning_content patch")
        return

    _patch_combine_chunks(openai_models)
    _patch_build_messages(openai_models)
    logger.debug("Patched llm library for reasoning_content support")


def _patch_combine_chunks(openai_models):
    original = openai_models.combine_chunks

    def patched_combine_chunks(chunks):
        result = original(chunks)
        reasoning_parts = []
        for item in chunks:
            for choice in getattr(item, "choices", []):
                delta = getattr(choice, "delta", None)
                if delta is not None:
                    rc = getattr(delta, "reasoning_content", None)
                    if rc:
                        reasoning_parts.append(rc)
        if reasoning_parts:
            result["reasoning_content"] = "".join(reasoning_parts)
        return result

    openai_models.combine_chunks = patched_combine_chunks


def _patch_build_messages(openai_models):
    original_build = openai_models._Shared.build_messages

    def patched_build_messages(self, prompt, conversation=None):
        messages = original_build(self, prompt, conversation)

        if conversation is not None:
            prev_responses = list(conversation.responses)
            msg_idx = 0

            for prev_response in prev_responses:
                rj = getattr(prev_response, "response_json", None) or {}
                rc = rj.get("reasoning_content")

                has_text = bool(prev_response.text_or_raise())
                has_tools = bool(prev_response.tool_calls_or_raise())
                num_assistant = (1 if has_text else 0) + (1 if has_tools else 0)

                # Skip non-assistant messages to find the right position
                while msg_idx < len(messages) and messages[msg_idx].get("role") != "assistant":
                    msg_idx += 1

                if rc and num_assistant:
                    for _ in range(num_assistant):
                        if msg_idx < len(messages) and messages[msg_idx].get("role") == "assistant":
                            messages[msg_idx]["reasoning_content"] = rc
                            msg_idx += 1
                else:
                    msg_idx += num_assistant

        return messages

    openai_models._Shared.build_messages = patched_build_messages
