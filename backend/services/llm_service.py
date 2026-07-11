"""
services/llm_service.py — IBM watsonx.ai wrapper.

Single point of contact with the IBM SDK.
Swap models by changing WATSONX_MODEL_ID in .env — no code changes needed.
"""

from typing import Optional
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

from backend.config import Config
from backend.utils.logger import get_logger

log = get_logger(__name__)


class LLMService:
    """Thin, model-agnostic wrapper around IBM watsonx ModelInference."""

    def __init__(self):
        # Validate config before touching the SDK
        missing = []
        if not Config.WATSONX_API_KEY:    missing.append("WATSONX_API_KEY")
        if not Config.WATSONX_PROJECT_ID: missing.append("WATSONX_PROJECT_ID")
        if not Config.WATSONX_URL:        missing.append("WATSONX_URL")
        if missing:
            raise RuntimeError(
                f"IBM watsonx.ai credentials missing in .env: {', '.join(missing)}"
            )

        log.info(
            "Connecting to IBM watsonx.ai — url=%s model=%s project=%s...",
            Config.WATSONX_URL,
            Config.WATSONX_MODEL_ID,
            Config.WATSONX_PROJECT_ID[:8] + "...",
        )

        try:
            credentials = Credentials(
                url=Config.WATSONX_URL,
                api_key=Config.WATSONX_API_KEY,
            )
            self._model = ModelInference(
                model_id=Config.WATSONX_MODEL_ID,
                credentials=credentials,
                project_id=Config.WATSONX_PROJECT_ID,
            )
        except Exception as e:
            err = str(e)
            if "not valid" in err.lower() or "url" in err.lower():
                raise RuntimeError(
                    f"IBM watsonx.ai URL is invalid: '{Config.WATSONX_URL}'. "
                    f"Check WATSONX_URL in your .env — must be your region endpoint, "
                    f"e.g. https://us-south.ml.cloud.ibm.com"
                ) from e
            if "404" in err or "not found" in err.lower():
                raise RuntimeError(
                    f"IBM watsonx.ai project not found: '{Config.WATSONX_PROJECT_ID}'. "
                    f"Check that WATSONX_PROJECT_ID matches the project in region "
                    f"'{Config.WATSONX_URL}'. Log in to dataplatform.cloud.ibm.com to verify."
                ) from e
            if "401" in err or "unauthorized" in err.lower() or "access denied" in err.lower():
                raise RuntimeError(
                    f"IBM watsonx.ai authentication failed. Check that WATSONX_API_KEY "
                    f"is a valid IBM Cloud API key with watsonx.ai access."
                ) from e
            raise RuntimeError(f"IBM watsonx.ai setup error: {err}") from e

        log.info("LLMService ready — model: %s", Config.WATSONX_MODEL_ID)

    def generate(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Call the LLM and return the generated text.
        Raises RuntimeError with a user-facing message on quota or API errors.
        """
        params = {
            GenParams.MAX_NEW_TOKENS:     max_new_tokens or Config.LLM_MAX_NEW_TOKENS,
            GenParams.TEMPERATURE:        temperature    if temperature is not None else Config.LLM_TEMPERATURE,
            GenParams.TOP_P:              Config.LLM_TOP_P,
            GenParams.REPETITION_PENALTY: Config.LLM_REPETITION_PENALTY,
            GenParams.STOP_SEQUENCES:     [
                "[INST]", "<|user|>",
                "The best answer is", "The correct answer is",
                "\n\nQuestion:", "QUESTION:",
            ],
        }

        log.debug("LLM generate — max_tokens=%d temp=%.1f",
                  params[GenParams.MAX_NEW_TOKENS], params[GenParams.TEMPERATURE])

        try:
            response = self._model.generate_text(prompt=prompt, params=params)
            text = (response or "").strip()
            log.debug("LLM response length: %d chars", len(text))
            return text
        except Exception as exc:
            err = str(exc)
            if "429" in err or "Too Many Requests" in err or "rate limit" in err.lower():
                raise RuntimeError(
                    "The AI service has temporarily reached its free usage limit. "
                    "Please try again later."
                )
            if "404" in err or "not found" in err.lower():
                raise RuntimeError(
                    f"IBM watsonx.ai model '{Config.WATSONX_MODEL_ID}' not found. "
                    f"Check WATSONX_MODEL_ID in your .env file."
                )
            log.error("IBM watsonx error: %s", err)
            raise RuntimeError(f"IBM watsonx error: {err}")


# Lazy singleton — not created at import time so startup never fails
_instance: Optional[LLMService] = None


def get_llm() -> LLMService:
    global _instance
    if _instance is None:
        _instance = LLMService()
    return _instance
