import logging
import time
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaClient:
    """HTTP client for the local Ollama inference server."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_host).rstrip("/")

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """
        Call Ollama /api/generate and return response text + token metadata.
        Returns:
            {
                "text": str,
                "prompt_tokens": int,
                "completion_tokens": int,
                "total_tokens": int,
                "model": str,
            }
        """
        model = model or settings.ollama_default_model
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        logger.info("Ollama generate | model=%s | prompt_len=%d", model, len(prompt))

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.error("Ollama request timed out after 300s")
            raise RuntimeError("Ollama request timed out. The model may be loading — try again.")
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP error: %s", e)
            raise RuntimeError(f"Ollama returned error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error("Ollama connection error: %s", e)
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}. Is it running?")

        return {
            "text": data.get("response", ""),
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            "model": data.get("model", model),
        }

    # ------------------------------------------------------------------
    # Model listing
    # ------------------------------------------------------------------

    async def list_models(self) -> list[str]:
        """Return list of model names available in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                logger.info("Ollama models available: %s", models)
                return models
        except Exception as e:
            logger.error("Failed to list Ollama models: %s", e)
            return []

    # ------------------------------------------------------------------
    # Health ping
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Return True if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Context window lookup
    # ------------------------------------------------------------------

    def get_context_window(self, model_name: str) -> int:
        """Return context window size in tokens for the given model."""
        return settings.context_windows.get(model_name, 8192)


# Module-level singleton
ollama_client = OllamaClient()