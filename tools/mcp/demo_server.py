#!/usr/bin/env python3
"""Демонстрационный MCP-сервер: JSON-RPC 2.0 по stdio, newline-delimited.

Показывает, как доменной реализации подключается к движку снаружи:
сервер отдаёт факты, правила читают их как обычные факты сцены.

    python3 tools/mcp/demo_server.py
"""

import json
import math
import sys

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "solar_elevation",
        "description": "Высота Солнца над горизонтом в градусах для заданной точки и времени.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "day_of_year": {"type": "integer"},
                "hour": {"type": "number"},
            },
            "required": ["latitude", "day_of_year", "hour"],
        },
    },
    {
        "name": "greeting",
        "description": "Приветствие демонстрационного провайдера.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def solar_elevation(latitude, day_of_year, hour):
    declination = 23.44 * math.sin(math.radians(360 * (284 + day_of_year) / 365))
    hour_angle = 15 * (hour - 12)
    lat = math.radians(latitude)
    dec = math.radians(declination)
    ha = math.radians(hour_angle)
    sin_alt = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(ha)
    return round(math.degrees(math.asin(max(-1.0, min(1.0, sin_alt)))), 2)


def handle(method, params):
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "elementarno-demo", "version": "0.1.0"},
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name == "solar_elevation":
            value = solar_elevation(
                float(arguments.get("latitude", 0)),
                int(arguments.get("day_of_year", 1)),
                float(arguments.get("hour", 12)),
            )
        elif name == "greeting":
            value = "elementarno"
        else:
            return {"content": [{"type": "text", "text": json.dumps({"error": f"unknown tool {name}"})}],
                    "isError": True}
        return {"content": [{"type": "text", "text": json.dumps({"value": value})}]}
    return {"error": f"unsupported method {method}"}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = message.get("method")
        if "id" not in message:
            continue
        response = {"jsonrpc": "2.0", "id": message["id"]}
        try:
            response["result"] = handle(method, message.get("params", {}))
        except Exception as exc:  # noqa: BLE001 — сервер обязан не падать
            response["error"] = {"code": -32000, "message": str(exc)}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
