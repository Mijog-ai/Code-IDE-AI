# agent.py
# Agentic QThread worker: Groq LLM + DuckDuckGo web-search tool.
#
# Loop:
#   1. Call Groq (non-streaming) with web_search tool available.
#   2. If the model issues a tool call  → execute web_search → feed results back.
#   3. Repeat until the model returns a normal (non-tool) response.
#   4. Stream that final response token-by-token to the UI.

from __future__ import annotations

import json
import threading

from PyQt6.QtCore import QThread, pyqtSignal

# ── Tool schema exposed to the model ─────────────────────────────────────────
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search DuckDuckGo for current information, recent events, "
                "live data, or any topic that requires up-to-date web results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to fetch (1-10, default 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    }
]

_AGENT_SYSTEM = (
    "You are a helpful AI assistant and expert Python engineer. "
    "You have access to DuckDuckGo web search via the web_search tool. "
    "Use it whenever the user asks about current events, live data, or any topic "
    "that benefits from up-to-date information. "
    "When writing code, wrap it in a ```python code block."
)


def _format_search_results(results: list[dict], query: str) -> str:
    if not results:
        return f"[No results found for: {query}]"
    lines = [f"DuckDuckGo results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['url']}")
        if r["snippet"]:
            lines.append(f"   {r['snippet']}")
        lines.append("")
    return "\n".join(lines)


class AgentWorker(QThread):
    """
    Runs a tool-calling agent loop in a background thread.

    Signals
    -------
    progress(int, str)  — progress bar updates (percent, message)
    status(str)         — informational messages shown in the chat history
    token(str)          — streamed chunks of the final answer
    finished(str)       — full final answer text
    error(str)          — error message on failure
    """

    progress = pyqtSignal(int, str)
    status   = pyqtSignal(str)
    token    = pyqtSignal(str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(
        self,
        messages: list[dict],
        api_key: str,
        model: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.messages    = list(messages)
        self.api_key     = api_key
        self.model       = model
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    # ── Thread entry ─────────────────────────────────────────────────────────

    def run(self) -> None:
        try:
            self._agent_loop()
        except Exception as exc:
            self.error.emit(str(exc))

    # ── Core loop ────────────────────────────────────────────────────────────

    def _agent_loop(self) -> None:
        import requests

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

        # Build working message list with the agent system prompt.
        # Drop any existing system message from the caller.
        messages = [{"role": "system", "content": _AGENT_SYSTEM}]
        for m in self.messages:
            if m["role"] != "system":
                messages.append(m)

        self.progress.emit(5, "Agent starting…")

        for iteration in range(6):
            if self._stop_event.is_set():
                self.finished.emit("")
                return

            # ── Non-streaming call (tool-calling round) ───────────────────
            payload = {
                "model":       self.model,
                "messages":    messages,
                "tools":       _TOOLS,
                "tool_choice": "auto",
                "stream":      False,
            }

            pct = min(60, 10 + iteration * 10)
            self.progress.emit(pct, "Thinking…")

            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()

            data   = resp.json()
            choice = data["choices"][0]
            msg    = choice["message"]
            reason = choice.get("finish_reason", "")

            if reason == "tool_calls":
                # Append the assistant message that contains tool_calls
                messages.append(msg)

                for tc in msg.get("tool_calls", []):
                    if self._stop_event.is_set():
                        self.finished.emit("")
                        return

                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"] or "{}")

                    if fn_name == "web_search":
                        query  = fn_args.get("query", "")
                        max_r  = int(fn_args.get("max_results", 5))
                        label  = f"🔍 Searching: {query}"
                        self.status.emit(label)
                        self.progress.emit(40, label)

                        from web_search import search as ddg_search
                        results     = ddg_search(query, max_results=max_r)
                        result_text = _format_search_results(results, query)

                        messages.append({
                            "role":         "tool",
                            "tool_call_id": tc["id"],
                            "content":      result_text,
                        })

            else:
                # No tool calls — stream the final answer
                self.progress.emit(70, "Generating response…")
                self.status.emit("Generating response…")

                stream_payload = {
                    "model":    self.model,
                    "messages": messages,
                    "stream":   True,
                }

                full_response = ""
                token_count   = 0

                with requests.post(
                    url, headers=headers, json=stream_payload,
                    stream=True, timeout=120,
                ) as sr:
                    sr.raise_for_status()
                    for raw_line in sr.iter_lines():
                        if self._stop_event.is_set():
                            break
                        if not raw_line:
                            continue
                        line = raw_line.decode("utf-8", errors="replace")
                        if not line.startswith("data: "):
                            continue
                        d = line[6:]
                        if d.strip() == "[DONE]":
                            break
                        try:
                            obj  = json.loads(d)
                            text = obj["choices"][0]["delta"].get("content") or ""
                            if text:
                                full_response += text
                                token_count   += 1
                                self.token.emit(text)
                                if token_count % 8 == 0:
                                    pct = min(95, 70 + int(token_count / 200 * 25))
                                    self.progress.emit(pct, "Generating…")
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

                if self._stop_event.is_set():
                    self.progress.emit(100, "Agent stopped.")
                else:
                    self.progress.emit(100, "Done.")

                self.finished.emit(full_response)
                return

        self.error.emit("Agent: too many tool-call iterations without a final answer.")
