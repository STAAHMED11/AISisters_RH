"""Single entry point to the LLM: every call goes through `LLM`, so a provider or model change happens here only.

- `structured()` uses native structured outputs (`messages.parse`) with a Pydantic model => validated JSON.
- `chat()` is a plain text turn (text-mode pre-interview).
- Tiers: "smart" (Sonnet) for judgement, "fast" (Haiku) for high-volume tasks. Models come from MODEL_SMART / MODEL_FAST.
"""
import base64
import logging
import time
from typing import TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from . import costs
from .config import settings

log = logging.getLogger("llm")
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


class LLM:
    def __init__(self):
        self._client: Anthropic | None = None

    @property
    def client(self) -> Anthropic:
        if self._client is None:
            if not settings.anthropic_api_key:
                raise LLMError("ANTHROPIC_API_KEY manquante (.env)")
            self._client = Anthropic(api_key=settings.anthropic_api_key, timeout=settings.llm_timeout, max_retries=1)
        return self._client

    def model(self, tier: str) -> str:
        return settings.model_smart if tier == "smart" else settings.model_fast

    @staticmethod
    def _content(user: str, files: list[tuple[str, bytes]] | None):
        """files: list of (mime, bytes) — PDF or image, sent natively to Claude."""
        if not files:
            return user
        blocks = []
        for mime, data in files:
            b64 = base64.standard_b64encode(data).decode()
            kind = "document" if mime == "application/pdf" else "image"
            blocks.append({"type": kind, "source": {"type": "base64", "media_type": mime, "data": b64}})
        blocks.append({"type": "text", "text": user})
        return blocks

    def structured(
        self,
        tier: str,
        system: str,
        user: str,
        schema: type[T],
        *,
        files: list[tuple[str, bytes]] | None = None,
        max_tokens: int = 4096,
        usage: dict | None = None,
    ) -> T:
        last_err: Exception | None = None
        messages = [{"role": "user", "content": self._content(user, files)}]
        # Thinking tokens count against max_tokens: keep a generous floor so JSON is never cut mid-string.
        budget = max(max_tokens, 10000 if tier == "smart" else 2500)
        for _attempt in range(2):
            t0 = time.time()
            try:
                # Native structured outputs (forced tool_choice is rejected by the 5.x models).
                kwargs = {"thinking": {"type": "disabled"}} if tier != "smart" else {}
                resp = self.client.messages.parse(
                    model=self.model(tier),
                    max_tokens=budget,
                    system=system,
                    messages=messages,
                    output_format=schema,
                    **kwargs,
                )
                costs.record_llm(self.model(tier), resp.usage, usage)  # billed even if we retry
                if resp.stop_reason == "max_tokens":
                    budget *= 2
                    raise ValueError("truncated (max_tokens): retrying with a larger budget")
                if resp.stop_reason == "refusal" or resp.parsed_output is None:
                    raise ValueError(f"no parsed output (stop_reason={resp.stop_reason})")
                log.info("llm %s %s %.1fs in=%s out=%s", tier, schema.__name__, time.time() - t0,
                         resp.usage.input_tokens, resp.usage.output_tokens)
                return resp.parsed_output
            except (ValidationError, ValueError) as e:
                last_err = e
                budget *= 2
                log.warning("llm structured retry (%s): %s", schema.__name__, e)
            except LLMError:
                raise
            except Exception as e:  # network, timeout, API error
                last_err = e
                log.warning("llm call failed (%s): %s", schema.__name__, e)
                time.sleep(1)
        raise LLMError(f"LLM a échoué ({schema.__name__}): {last_err}")

    def chat(self, tier: str, system: str, messages: list[dict], max_tokens: int = 600, usage: dict | None = None) -> str:
        try:
            kwargs = {"thinking": {"type": "disabled"}} if tier != "smart" else {}
            resp = self.client.messages.create(
                model=self.model(tier), max_tokens=max(max_tokens, 1500), system=system, messages=messages, **kwargs
            )
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"LLM chat a échoué: {e}") from e
        costs.record_llm(self.model(tier), resp.usage, usage)
        return "".join(b.text for b in resp.content if b.type == "text").strip()


llm = LLM()
