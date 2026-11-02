"""External knowledge providers: local facts and MCP servers.

The engine never hardcodes domain knowledge it could fetch. A domain
implementation may arrive as an MCP server (weather, image search, symbol
lookup, a perception model), and the rule layer consumes its output as
ordinary scene facts.
"""

import json
import subprocess

from .paths import values_equal


class ProviderError(RuntimeError):
    pass


class Provider:
    name = "provider"

    def capabilities(self):
        return []

    def call(self, capability, payload):
        raise NotImplementedError

    def close(self):
        pass


class LocalProvider(Provider):
    """Facts available in-process, configured in config/profiles.json."""

    def __init__(self, name, facts):
        self.name = name
        self._facts = facts or {}

    def capabilities(self):
        return sorted(self._facts)

    def call(self, capability, payload):
        if capability not in self._facts:
            raise ProviderError(f"{self.name}: no capability {capability}")
        value = self._facts[capability]
        if callable(value):
            value = value(payload)
        return value


class StdioMcpClient:
    """Minimal MCP client: newline-delimited JSON-RPC 2.0 over stdio."""

    def __init__(self, command, args=None, cwd=None, env=None):
        self.command = command
        self.args = args or []
        self.cwd = cwd
        self.env = env
        self.proc = None
        self._id = 0

    def start(self):
        try:
            self.proc = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                cwd=self.cwd,
                env=self.env,
            )
        except OSError as exc:
            raise ProviderError(f"cannot start MCP server {self.command}: {exc}") from exc
        self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "elementarno", "version": "0.1.0"},
        })
        self.notify("notifications/initialized", {})
        return self

    def _write(self, payload):
        if self.proc is None or self.proc.stdin is None:
            raise ProviderError("MCP server is not running")
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _read(self):
        if self.proc is None or self.proc.stdout is None:
            raise ProviderError("MCP server is not running")
        line = self.proc.stdout.readline()
        if not line:
            raise ProviderError("MCP server closed the connection")
        return json.loads(line)

    def request(self, method, params):
        self._id += 1
        request_id = self._id
        self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            message = self._read()
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise ProviderError(f"{method}: {message['error']}")
            return message.get("result", {})

    def notify(self, method, params):
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def list_tools(self):
        return self.request("tools/list", {}).get("tools", [])

    def call_tool(self, name, arguments):
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise ProviderError(f"tool {name} failed: {result}")
        pieces = []
        for item in result.get("content", []):
            if item.get("type") == "text":
                pieces.append(item.get("text", ""))
        text = "\n".join(pieces)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}

    def stop(self):
        if self.proc is not None:
            for stream in (self.proc.stdin, self.proc.stdout):
                try:
                    if stream is not None:
                        stream.close()
                except (OSError, ValueError):
                    pass
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None


class McpProvider(Provider):
    def __init__(self, name, client, capability_map=None):
        self.name = name
        self.client = client
        self.capability_map = capability_map or {}
        self._tools = None

    def capabilities(self):
        if self._tools is None:
            self.client.start()
            self._tools = self.client.list_tools()
        names = [t.get("name") for t in self._tools]
        return sorted(set(self.capability_map.keys()) | set(names))

    def _tool_for(self, capability):
        if capability in self.capability_map:
            return self.capability_map[capability]
        tools = self.client.list_tools()
        for tool in tools:
            if tool.get("name") == capability:
                return capability
        for tool in tools:
            if capability.endswith(tool.get("name", "\0")):
                return tool.get("name")
        raise ProviderError(f"{self.name}: no tool for capability {capability}")

    def call(self, capability, payload):
        tool = self._tool_for(capability)
        return self.client.call_tool(tool, payload or {})

    def close(self):
        self.client.stop()


def load_providers(config):
    providers = []
    for name, spec in (config.get("providers") or {}).items():
        providers.append(LocalProvider(name, spec.get("facts", {})))
    for name, spec in (config.get("mcp_servers") or {}).items():
        client = StdioMcpClient(
            spec["command"],
            spec.get("args", []),
            cwd=spec.get("cwd"),
            env=spec.get("env"),
        )
        providers.append(McpProvider(name, client, spec.get("capability_map", {})))
    return providers


def enrich(scene, providers, wanted):
    """Fetch external facts and attach them as a `facts` collection."""
    facts = list(scene.get("facts", []))
    errors = []
    for capability in wanted:
        for provider in providers:
            if capability not in provider.capabilities():
                continue
            try:
                value = provider.call(capability, scene)
            except ProviderError as exc:
                errors.append({"capability": capability, "provider": provider.name, "error": str(exc)})
                continue
            facts.append({
                "key": capability,
                "value": value,
                "provider": provider.name,
                "source": capability,
            })
            break
        else:
            errors.append({"capability": capability, "provider": None, "error": "capability unavailable"})
    enriched = dict(scene)
    enriched["facts"] = facts
    enriched["enrichment_errors"] = errors
    return enriched


def fact_value(scene, capability):
    for fact in scene.get("facts", []):
        if fact.get("key") == capability:
            return fact.get("value")
    return None


def fact_matches(scene, capability, expected):
    value = fact_value(scene, capability)
    if value is None:
        return False
    return values_equal(value, expected)
