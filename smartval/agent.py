"""Agentic workflow: a local Ollama LLM that uses the SmartValGuiden MCP tools.

Loop:
  1. Connect to the MCP server and discover its tools.
  2. Send the user question + tool definitions to the LLM.
  3. If the LLM asks for tool calls, run them through MCP and feed the JSON
     results back (retrieval-augmented generation).
  4. Repeat until the LLM gives a final answer grounded in the tool results.

    python -m smartval.agent "Vilken laptop under 10 000 kr passar för programmering?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Protocol

from mcp import Client
from mcp.client.stdio import StdioServerParameters

SYSTEM_PROMPT = (
    "Du är en hjälpsam köprådgivare för SmartValGuiden.se. Använd alltid verktygen "
    "för att hämta produktdata innan du svarar. Hitta aldrig på produkter, priser "
    "eller specifikationer. Svara kort på samma språk som användaren och ange "
    "produkt-id och pris i SEK för varje rekommendation."
)


class ChatClient(Protocol):
    async def chat(self, model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any: ...


def mcp_tool_to_ollama(tool: Any) -> dict[str, Any]:
    """Convert an MCP tool definition to the function-calling schema Ollama expects."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def _field(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


async def run_agent(
    question: str,
    mcp_client: Any,
    llm: ChatClient,
    model: str,
    max_steps: int = 6,
    verbose: bool = False,
) -> str:
    tools = [mcp_tool_to_ollama(t) for t in (await mcp_client.list_tools()).tools]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for _ in range(max_steps):
        response = await llm.chat(model=model, messages=messages, tools=tools)
        message = _field(response, "message")
        tool_calls = _field(message, "tool_calls") or []
        content = _field(message, "content") or ""

        if not tool_calls:
            return content

        messages.append({"role": "assistant", "content": content, "tool_calls": [
            {"function": {"name": _field(_field(c, "function"), "name"),
                          "arguments": _field(_field(c, "function"), "arguments")}}
            for c in tool_calls
        ]})
        for call in tool_calls:
            fn = _field(call, "function")
            name, args = _field(fn, "name"), _field(fn, "arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            if verbose:
                print(f"-> tool {name}({json.dumps(args, ensure_ascii=False)})", file=sys.stderr)
            result = await mcp_client.call_tool(name, args)
            text = "\n".join(getattr(c, "text", "") for c in result.content)
            messages.append({"role": "tool", "tool_name": name, "content": text})

    return "Jag kunde inte slutföra svaret inom det tillåtna antalet steg."


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Ask the SmartValGuiden AI agent a question")
    parser.add_argument("question")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen3:8b"))
    parser.add_argument("--mcp-url", default=os.environ.get("SMARTVAL_MCP_URL"),
                        help="streamable HTTP URL of the MCP server; default launches it over stdio")
    parser.add_argument("-v", "--verbose", action="store_true", help="print tool calls")
    args = parser.parse_args()

    from ollama import AsyncClient  # imported here so tests don't need a running Ollama

    target: Any = args.mcp_url or StdioServerParameters(
        command=sys.executable, args=["-m", "smartval.mcp_server"], env=dict(os.environ)
    )
    async with Client(target) as mcp_client:
        answer = await run_agent(args.question, mcp_client, AsyncClient(), args.model, verbose=args.verbose)
    print(answer)


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
