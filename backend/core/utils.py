# backend/core/utils.py
"""Shared utilities used across all agents."""
import re
import json


def parse_json(text: str) -> dict:
    """
    Parse JSON from LLM response.
    Handles markdown code fences and extracts the first JSON object.
    """
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise
