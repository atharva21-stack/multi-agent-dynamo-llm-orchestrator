"""Validation Agent for agent-inference-stack.

Validates execution outputs for quality, completeness, and accuracy.
"""
from __future__ import annotations

import json
import re
from typing import Any

import structlog
from pydantic import BaseModel, Field

from src.agents.base import AgentConfig, BaseAgent

logger = structlog.get_logger(__name__)

VALIDATION_SYSTEM_PROMPT = """You are a Validation Agent that evaluates the quality of AI-generated outputs.

Your role is to:
1. Check if the output addresses the original request completely
2. Assess accuracy and coherence
3. Identify any gaps or issues
4. Provide a quality score and actionable recommendations

Output JSON:
{
  "is_valid": true|false,
  "score": 0.0-1.0,
  "issues": ["issue 1", "issue 2"],
  "recommendations": ["recommendation 1"],
  "summary": "Brief validation summary"
}

Score guidelines:
- 0.9-1.0: Excellent, fully addresses request
- 0.7-0.9: Good, minor gaps
- 0.5-0.7: Adequate, notable gaps
- 0.3-0.5: Poor, significant issues
- 0.0-0.3: Failing, does not address request"""

VALIDATION_PROMPT_TEMPLATE = """Original Request: {original_request}

Execution Output:
{execution_output}

Validate whether this output adequately addresses the original request.
Return ONLY the JSON validation result."""


class ValidationResult(BaseModel):
    """Result from validation agent."""

    is_valid: bool
    score: float = Field(ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str = ""
    min_score_threshold: float = 0.7

    @property
    def passes_threshold(self) -> bool:
        return self.score >= self.min_score_threshold


class ValidationAgent(BaseAgent):
    """Agent that validates execution outputs."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                name="validation",
                model="claude-haiku-4-5-20251001",
                temperature=0.1,
                max_tokens=1024,
            )
        super().__init__(config)
        self.min_score_threshold = 0.7

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Validate task execution output.

        Args:
            input_data: Dict with keys:
                - original_request (str): The user's original request
                - execution_output (dict|str): Output from execution agents

        Returns:
            ValidationResult as dict.
        """
        original_request = input_data.get("original_request", "")
        execution_output = input_data.get("execution_output", {})

        self._log.info("validation_started")

        output_str = (
            json.dumps(execution_output, indent=2)
            if isinstance(execution_output, dict)
            else str(execution_output)
        )

        prompt = VALIDATION_PROMPT_TEMPLATE.format(
            original_request=original_request,
            execution_output=output_str[:3000],
        )

        response = await self._call_llm(
            prompt=prompt,
            system_prompt=VALIDATION_SYSTEM_PROMPT,
            temperature=0.1,
        )

        result = self._parse_validation_result(response)
        self._log.info(
            "validation_completed",
            is_valid=result.is_valid,
            score=result.score,
            issues_count=len(result.issues),
        )
        return result.model_dump()

    def _parse_validation_result(self, raw_response: str) -> ValidationResult:
        """Parse LLM response into ValidationResult."""
        cleaned = re.sub(r"```(?:json)?\n?", "", raw_response).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                score = float(data.get("score", 0.5))
                return ValidationResult(
                    is_valid=bool(data.get("is_valid", score >= self.min_score_threshold)),
                    score=score,
                    issues=data.get("issues", []),
                    recommendations=data.get("recommendations", []),
                    summary=data.get("summary", ""),
                    min_score_threshold=self.min_score_threshold,
                )
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback
        return ValidationResult(
            is_valid=False,
            score=0.5,
            issues=["Could not parse validation response"],
            recommendations=["Retry validation"],
            summary="Validation parsing failed",
            min_score_threshold=self.min_score_threshold,
        )
