from __future__ import annotations

import logging
from typing import Any

from agents import Agent
from agents import Runner
from agents.mcp import MCPServerStdio

from .model import get_openai_model
from .model import get_openai_model_settings


class OpenAIAgent:
    """A wrapper for OpenAI Agent"""

    def __init__(self, name: str, mcp_servers: list | None = None) -> None:
        self.current_agent = Agent(
            name=name,
            instructions="""
            You are a helpful Slack bot assistant. When responding, you must
            strictly use Slack’s mrkdwn formatting syntax only. Do not generate
            headings (#), tables, or any other Markdown features not supported by
            Slack. Ensure that all output strictly complies with Slack’s mrkdwn
            specifications.""",
            model=get_openai_model(),
            model_settings=get_openai_model_settings(),
            mcp_servers=(mcp_servers if mcp_servers is not None else []),
        )
        self.name = name

    @classmethod
    def from_dict(cls, name: str, config: dict[str, Any]) -> OpenAIAgent:
        mcp_servers = [
            MCPServerStdio(
                client_session_timeout_seconds=60.0,
                params={
                    "command": mcp_srv["command"],
                    "args": mcp_srv["args"],
                    "env": mcp_srv.get("env", {}),
                },
            )
            for mcp_srv in config.values()
        ]
        return cls(name, mcp_servers)

    async def connect(self) -> None:
        for mcp_server in self.current_agent.mcp_servers:
            try:
                await mcp_server.connect()
                logging.info(f"Server {mcp_server.name} connecting")
            except Exception as e:
                logging.error(f"Error during connecting of server {mcp_server.name}: {e}")

    async def run(self, messages: list) -> str:
        """Run a workflow starting at the given agent."""
        result = await Runner.run(self.current_agent, input=messages)
        return result.final_output

    async def cleanup(self) -> None:
        """Clean up resources."""
        # Clean up servers
        for mcp_server in self.current_agent.mcp_servers:
            try:
                await mcp_server.cleanup()
                logging.info(f"Server {mcp_server.name} cleaned up")
            except Exception as e:
                logging.error(f"Error during cleanup of server {mcp_server.name}: {e}")
