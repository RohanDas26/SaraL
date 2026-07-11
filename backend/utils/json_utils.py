"""
utils/json_utils.py — Fault-tolerant JSON extractor for LLM outputs.

LLMs (especially large instruct models like Llama 3.3) frequently return JSON
with minor syntax errors such as:
  - Markdown code block wrappers (```json ... ```)
  - Trailing commas before closing brackets/braces
  - Unescaped control characters or quotes inside string fields
  - Truncation at the end when max_new_tokens is reached

This module attempts strict parsing first, then falls back to object-by-object
recovery so that even if the 5th question in a quiz is truncated or malformed,
the first 4 valid questions are cleanly recovered and returned instead of throwing a 500 error.
"""

import re
import json
from typing import Optional, List, Dict, Any
from backend.utils.logger import get_logger

log = get_logger(__name__)


def parse_llm_json_array(raw: str) -> Optional[List[Dict[str, Any]]]:
    """
    Robustly extract and parse a JSON array of dicts from raw LLM output.
    Returns a list of dictionaries if at least one valid object is recovered,
    or None if parsing completely fails.
    """
    if not raw or not raw.strip():
        return None

    text = raw.strip()

    # 1. Strip markdown fences if present
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # 2. Find outermost '[' and ']'
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        array_str = text[start : end + 1]
        # Clean trailing commas: `, ]` -> `]` and `, }` -> `}`
        cleaned_array_str = _clean_json_string(array_str)
        try:
            parsed = json.loads(cleaned_array_str)
            if isinstance(parsed, list) and len(parsed) > 0:
                log.debug("Successfully parsed complete JSON array with %d items.", len(parsed))
                return parsed
        except json.JSONDecodeError as exc:
            log.warning("Strict array JSON decode failed (%s). Attempting object-by-object recovery...", exc)

    # 3. Fallback: Object-by-object extraction
    # This recovers items when the final item is truncated or has unrecoverable syntax errors.
    items: List[Dict[str, Any]] = []
    
    # Extract all top-level JSON objects {...} from the text using brace counting
    object_strings = _extract_json_objects(text)
    for obj_str in object_strings:
        cleaned_obj = _clean_json_string(obj_str)
        try:
            item = json.loads(cleaned_obj)
            if isinstance(item, dict) and item:
                items.append(item)
        except json.JSONDecodeError:
            # Try cleaning unescaped control characters/newlines within strings
            super_cleaned = re.sub(r"[\x00-\x1f]+", " ", cleaned_obj)
            try:
                item = json.loads(super_cleaned)
                if isinstance(item, dict) and item:
                    items.append(item)
            except json.JSONDecodeError:
                continue

    if items:
        log.info("Recovered %d valid objects via fallback JSON extraction.", len(items))
        return items

    log.error("Failed to extract any valid JSON objects from LLM response. Raw snippet: %s", text[:200])
    return None


def _clean_json_string(s: str) -> str:
    """
    Remove common LLM JSON formatting errors like trailing commas.
    """
    # Remove trailing comma before ']' or '}'
    s = re.sub(r",\s*([\]}])", r"\1", s)
    return s


def _extract_json_objects(text: str) -> List[str]:
    """
    Extract balanced {...} strings from text.
    Handles nested braces correctly.
    """
    objects = []
    depth = 0
    start_idx = -1
    in_string = False
    escape = False

    for i, char in enumerate(text):
        if char == '"' and not escape:
            in_string = not in_string
        elif char == "\\" and not escape:
            escape = True
            continue
        
        if not in_string:
            if char == "{":
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx != -1:
                        objects.append(text[start_idx : i + 1])
                        start_idx = -1

        escape = False

    return objects
