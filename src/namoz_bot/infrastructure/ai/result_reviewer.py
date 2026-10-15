"""The reviewer emits bounded issues and cannot rewrite authoritative facts."""

import json

from namoz_bot.application.roles.manager import REVIEW_INSTRUCTION
from namoz_bot.domain.agent_protocol import AgentResult
from namoz_bot.domain.workforce.tasks import ReviewVerdict, TaskPlan
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient


class GeminiResultReviewer:
    def __init__(self, transport: GeminiClient):
        self.transport = transport

    async def review(self, plan: TaskPlan, result: AgentResult) -> ReviewVerdict:
        payload = await self.transport.generate_json(
            model=plan.models["manager"].model_id,
            instruction=plan.review_instruction or REVIEW_INSTRUCTION,
            schema={
                "type": "OBJECT",
                "properties": {
                    "decision": {"type": "STRING", "enum": ["accept", "revise", "clarify"]},
                    "issues": {"type": "ARRAY", "items": {"type": "STRING"}, "maxItems": 5},
                },
                "required": ["decision", "issues"],
            },
            parts=[
                {
                    "text": json.dumps(
                        {
                            "request": plan.transcript,
                            "selection": plan.selection.model_dump(mode="json"),
                            "evidence": result.model_dump(mode="json"),
                        },
                        ensure_ascii=False,
                    )
                }
            ],
            max_output_tokens=1024,
        )
        return ReviewVerdict.model_validate(payload)
