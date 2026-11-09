"""Client for NOVA's optional local LM Studio model server."""
from __future__ import annotations

import json
import os
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from pathlib import Path

def _load_env() -> None:
    path = Path(__file__).resolve().parent / ".env"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, _, value = line.partition("=")
                os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_env()

BASE_URL = os.environ.get("NOVA_LOCAL_AI_URL", "http://127.0.0.1:1234/v1").rstrip("/")


class LocalAIError(RuntimeError):
    """Raised when the local model server cannot answer a request."""


class WebSearchError(RuntimeError):
    """Raised when web search is not configured or cannot return results."""


def search_web_context(query: str, timeout: float = 25.0) -> tuple[str, list[dict[str, str]]]:
    """Fetch compact, source-linked context from Brave for a local LLM."""
    api_key = os.environ.get("NOVA_BRAVE_API_KEY", "").strip()
    if not api_key:
        raise WebSearchError(
            "Live web search is not set up yet. Create a Brave Search API key, then start NOVA "
            "from PowerShell with NOVA_BRAVE_API_KEY set; see the README for steps."
        )
    params = urlencode({
        "q": query[:600],
        "country": "IN",
        "search_lang": "en",
        "count": 6,
        "maximum_number_of_urls": 6,
        "maximum_number_of_tokens": 3000,
        "context_threshold_mode": "balanced",
        "safesearch": "moderate",
    })
    request = Request(
        f"https://api.search.brave.com/res/v1/llm/context?{params}",
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403):
            raise WebSearchError("Brave rejected the API key. Check NOVA_BRAVE_API_KEY and your Brave API plan.") from error
        if error.code == 429:
            raise WebSearchError("Brave web search rate limit reached. Check your API plan or try again later.") from error
        raise WebSearchError(f"Brave web search returned HTTP {error.code}.") from error
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise WebSearchError("Could not reach Brave web search. Check your internet connection and try again.") from error

    grounding = payload.get("grounding", {}) if isinstance(payload, dict) else {}
    items = grounding.get("generic", []) if isinstance(grounding, dict) else []
    sources: list[dict[str, str]] = []
    context: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title") or url
        snippets = item.get("snippets", [])
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            continue
        if not isinstance(snippets, list):
            snippets = []
        text = " ".join(str(snippet).strip() for snippet in snippets if snippet)
        if not text:
            continue
        number = len(sources) + 1
        sources.append({"title": str(title), "url": url})
        context.append(f"[{number}] {title}\nURL: {url}\n{text[:4000]}")
    if not context:
        raise WebSearchError("Web search returned no useful pages for that question. Try a more specific search.")
    return "\n\n".join(context), sources


def list_models(timeout: float = 2.5) -> list[str]:
    request = Request(f"{BASE_URL}/models", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise LocalAIError("Local AI is not connected. Start LM Studio, load a model, and enable its local server.") from error

    models = payload.get("data", []) if isinstance(payload, dict) else []
    identifiers = [item.get("id") for item in models if isinstance(item, dict) and item.get("id")]
    if not identifiers:
        raise LocalAIError("LM Studio is running, but no model is available. Load a model in LM Studio first.")
    return identifiers


_model_cache: str | None = None


def default_model() -> str:
    """First loaded chat model (skips embedding models), cached."""
    global _model_cache
    if _model_cache is None:
        names = [m for m in list_models() if "embed" not in m.lower()]
        if not names:
            raise LocalAIError("No chat model is loaded in LM Studio.")
        _model_cache = names[0]
    return _model_cache


class ThinkStripper:
    """Drops <think>...</think> even when the tags are split across chunks."""
    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self.buf, self.inside = "", False

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        out = ""
        while True:
            tag = self.CLOSE if self.inside else self.OPEN
            i = self.buf.find(tag)
            if i != -1:
                if not self.inside:
                    out += self.buf[:i]
                self.buf = self.buf[i + len(tag):]
                self.inside = not self.inside
                continue
            keep = max((k for k in range(1, len(tag)) if self.buf.endswith(tag[:k])), default=0)
            if not self.inside:
                out += self.buf[:len(self.buf) - keep]
            self.buf = self.buf[len(self.buf) - keep:]
            return out

    def flush(self) -> str:
        return "" if self.inside else self.buf


_no_reasoning: set[str] = set()   # models that have no thinking switch


def stream_chat(messages: list[dict[str, str]], model: str | None = None,
                max_tokens: int = 1024, temperature: float = 0.6) -> Iterator[str]:
    """Stream a reply from LM Studio's native chat API."""
    global _model_cache
    selected = model or default_model()
    system_prompt = "\n\n".join(
        m["content"] for m in messages if m.get("role") == "system"
    )
    conversation = [
        f"{'User' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')}"
        for m in messages if m.get("role") in ("user", "assistant")
    ]
    payload = {
        "model": selected,
        "input": "\n\n".join(conversation),
        "system_prompt": system_prompt,
        "stream": True,
        "store": False,
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if selected not in _no_reasoning:
        payload["reasoning"] = "off"
    request = Request(
        f"{BASE_URL.removesuffix('/v1')}/api/v1/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    strip = ThinkStripper()
    streamed = False
    try:
        with urlopen(request, timeout=120) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                kind = event.get("type")
                if kind == "error":
                    detail = event.get("error", {}).get("message", "LM Studio reported an API error.")
                    raise LocalAIError(str(detail))
                if kind == "message.delta":
                    chunk = event.get("content")
                    if isinstance(chunk, str) and chunk:
                        text = strip.feed(chunk)
                        if text:
                            streamed = True
                            yield text
                elif kind == "chat.end" and not streamed:
                    output = (event.get("result") or {}).get("output", [])
                    final = "".join(
                        item.get("content", "") for item in output
                        if isinstance(item, dict) and item.get("type") == "message"
                        and isinstance(item.get("content"), str)
                    )
                    if final:
                        yield final
        tail = strip.flush()
        if tail:
            yield tail
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace").strip()
        if "reasoning" in detail and selected not in _no_reasoning:
            _no_reasoning.add(selected)   # no thinking switch on this model: retry without it
            yield from stream_chat(messages, selected, max_tokens, temperature)
            return
        _model_cache = None
        raise LocalAIError(detail or f"LM Studio returned HTTP {error.code}.") from error
    except (URLError, TimeoutError, OSError) as error:
        _model_cache = None
        raise LocalAIError("Could not reach the local model. Check that the server is running.") from error