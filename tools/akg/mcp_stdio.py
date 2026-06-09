# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

"""OpenCode-friendly MCP stdio server support.

The server speaks JSON-RPC over MCP stdio framing (`Content-Length: ...\r\n\r\n<body>`). For developer tests it
also accepts newline-delimited JSON and mirrors that output mode for the current process.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterator
from typing import Any

JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"
ToolHandler = Callable[[dict[str, Any]], Any]


def text_content(value: Any) -> list[dict[str, str]]:
    text = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True)
    return [{"type": "text", "text": text}]


def make_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": code, "message": message}}


class SimpleMcpServer:
    def __init__(self, name: str, tools: dict[str, tuple[dict[str, Any], ToolHandler]]) -> None:
        self.name = name
        self.tools = tools
        self._line_mode = False

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        if request_id is None and isinstance(method, str) and method.startswith("notifications/"):
            return None
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                    "serverInfo": {"name": self.name, "version": "1.0.0"},
                }
            elif method == "tools/list":
                result = {"tools": [tool_schema for tool_schema, _handler in self.tools.values()]}
            elif method == "tools/call":
                result = self._call_tool(request.get("params", {}))
            elif method == "resources/list":
                result = {"resources": []}
            elif method == "prompts/list":
                result = {"prompts": []}
            elif method in {"ping", "completion/complete"}:
                result = {}
            else:
                return make_error(request_id, -32601, f"unsupported method: {method}")
            return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}
        except KeyError as exc:
            return make_error(request_id, -32602, f"missing required argument: {exc.args[0]}")
        except Exception as exc:
            return make_error(request_id, -32000, str(exc))

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name not in self.tools:
            raise ValueError(f"unknown tool: {tool_name}")
        _schema, handler = self.tools[tool_name]
        value = handler(arguments)
        return {
            "content": text_content(value),
            "structuredContent": value if isinstance(value, dict) else None,
            "isError": False,
        }

    def serve(self) -> int:
        for request in self._read_requests():
            response = self.handle(request)
            if response is not None:
                self._write_response(response)
        return 0

    def _read_requests(self) -> Iterator[dict[str, Any]]:
        stream = sys.stdin.buffer
        while True:
            first_line = stream.readline()
            if not first_line:
                return
            if not first_line.strip():
                continue
            if first_line.lower().startswith(b"content-length:"):
                self._line_mode = False
                length = int(first_line.decode("ascii").split(":", 1)[1].strip())
                while True:
                    header = stream.readline()
                    if header in {b"\r\n", b"\n", b""}:
                        break
                    if header.lower().startswith(b"content-length:"):
                        length = int(header.decode("ascii").split(":", 1)[1].strip())
                body = stream.read(length)
                yield json.loads(body.decode("utf-8"))
            else:
                self._line_mode = True
                yield json.loads(first_line.decode("utf-8"))

    def _write_response(self, response: dict[str, Any]) -> None:
        body = json.dumps(response, separators=(",", ":")).encode("utf-8")
        if self._line_mode:
            sys.stdout.write(body.decode("utf-8") + "\n")
            sys.stdout.flush()
            return
        sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        sys.stdout.buffer.flush()


def schema(
    name: str, description: str, properties: dict[str, Any] | None = None, required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
            "additionalProperties": True,
        },
    }


def string_property(description: str, default: str | None = None) -> dict[str, Any]:
    prop: dict[str, Any] = {"type": "string", "description": description}
    if default is not None:
        prop["default"] = default
    return prop


def integer_property(description: str, default: int | None = None, minimum: int | None = None) -> dict[str, Any]:
    prop: dict[str, Any] = {"type": "integer", "description": description}
    if default is not None:
        prop["default"] = default
    if minimum is not None:
        prop["minimum"] = minimum
    return prop


def boolean_property(description: str, default: bool | None = None) -> dict[str, Any]:
    prop: dict[str, Any] = {"type": "boolean", "description": description}
    if default is not None:
        prop["default"] = default
    return prop
