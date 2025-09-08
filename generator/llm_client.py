# generator/llm_client.py
import json
import re
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI

JSON_MODE = {"type": "json_object"}

class LLMClient:
    """
    Thin wrapper around ChatOpenAI to:
      - request JSON-mode
      - defensively coerce messy outputs to valid JSON
    """

    def __init__(self, model: str, api_key: Optional[str] = None, temperature: float = 0.2):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature

    def _make_llm(self, json_mode: bool = False) -> ChatOpenAI:
        if json_mode:
            return ChatOpenAI(model=self.model, api_key=self.api_key,
                              temperature=self.temperature,
                              model_kwargs={"response_format": JSON_MODE})
        return ChatOpenAI(model=self.model, api_key=self.api_key,
                          temperature=self.temperature)

    def call_text(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> str:
        llm = self._make_llm(json_mode=False)
        if temperature is not None:
            llm.temperature = temperature
        resp = llm.invoke(messages)
        return resp.content if hasattr(resp, "content") else str(resp)

    def call_json(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Dict[str, Any]:
        """
        Prefer JSON mode. If provider returns text, we still coerce to JSON by extracting the first {...} block.
        """
        llm = self._make_llm(json_mode=True)
        if temperature is not None:
            llm.temperature = temperature
        resp = llm.invoke(messages)
        raw = resp.content if hasattr(resp, "content") else str(resp)
        return self._coerce_json(raw)

    @staticmethod
    def _coerce_json(raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        # Exact JSON? try directly
        try:
            return json.loads(raw)
        except Exception:
            pass
        # Extract largest trailing { ... } block
        m = re.search(r"\{[\s\S]*\}\s*$", raw)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # Try loose fixes (common for escaped newlines)
        raw2 = raw.replace("\n", " ").replace("\r", " ")
        m2 = re.search(r"\{[\s\S]*\}", raw2)
        if m2:
            return json.loads(m2.group(0))
        # Last resort
        raise ValueError(f"Failed to parse JSON from LLM output:\n{raw[:1000]}")
