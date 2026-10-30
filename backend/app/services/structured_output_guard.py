"""
Structured-output guard for the Graphiti LLM client.
"""

from typing import Any

from graphiti_core.prompts.models import Message
from pydantic import ValidationError

from ..utils.logger import get_logger

logger = get_logger('futuresreport.structured_output_guard')

# For OpenAI-compatible providers Graphiti uses response_format=json_object and
# appends the raw JSON Schema to the prompt ("Respond with a JSON object in the
# following format: {schema}"), but never checks the answer. qwen3.8-flash
# (production, 2026-10-30) sometimes answered with the schema itself
# ({"$defs": ..., "type": "object"}), which then failed Graphiti's parse
# ("ExtractedEntities extracted_entities Field required") and killed the build.

STRUCTURED_OUTPUT_RULE = (
    "OUTPUT FORMAT RULE: when the request gives a JSON Schema for the answer, reply with "
    "a JSON object (an instance) that follows that schema and contains the actual data. "
    "Never reply with the schema itself (no \"$defs\", \"properties\" or \"type\": \"object\" "
    "keys unless the schema defines them as data fields)."
)
SCHEMA_ECHO_CORRECTION = (
    "Your previous reply repeated the JSON Schema instead of answering. Do not return the "
    "schema. Return ONLY a JSON object containing the actual extracted data, using the "
    "field names defined in the schema."
)


def _looks_like_schema_echo(result: Any) -> bool:
    return isinstance(result, dict) and (
        "$defs" in result or ("properties" in result and result.get("type") == "object")
    )


def apply_structured_output_guard(llm_client: Any, max_retries: int = 2) -> Any:
    """Validate structured answers against the response model; on a schema echo or
    malformed answer, re-ask with an explicit correction. If it still doesn't
    validate, return the last answer unchanged (Graphiti decides as before), so
    this never fails a call that used to succeed."""
    original = llm_client.generate_response

    async def generate_response(messages, response_model=None, *args, **kwargs):
        if response_model is None:
            return await original(messages, response_model, *args, **kwargs)

        base = [Message(role=m.role, content=m.content) for m in messages]
        for i, message in enumerate(base):
            if message.role == "system":
                base[i] = Message(role="system", content=f"{message.content}\n\n{STRUCTURED_OUTPUT_RULE}")
                break
        else:
            base.insert(0, Message(role="system", content=STRUCTURED_OUTPUT_RULE))

        attempt_messages = base
        result = None
        for attempt in range(max_retries + 1):
            # fresh copies: provider clients append the schema to the last message in place
            result = await original(
                [Message(role=m.role, content=m.content) for m in attempt_messages],
                response_model, *args, **kwargs,
            )
            try:
                response_model.model_validate(result)
                return result
            except ValidationError as exc:
                if attempt == max_retries:
                    break
                echoed = _looks_like_schema_echo(result)
                logger.warning(
                    f"{response_model.__name__}: {'schema echoed' if echoed else 'invalid structured output'}, re-asking"
                )
                note = SCHEMA_ECHO_CORRECTION if echoed else (
                    f"Your previous reply did not match the required format ({str(exc)[:300]}). "
                    "Reply again with ONLY a valid JSON object following the schema."
                )
                attempt_messages = base + [Message(role="user", content=note)]
        return result

    llm_client.generate_response = generate_response
    return llm_client
