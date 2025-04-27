# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "aiohttp",
#     "mcp",
#     "openai-agents",
#     "python-dotenv",
#     "slack-bolt",
# ]
# ///
from __future__ import annotations

import asyncio
import os
import json
from typing import Any, Dict, List

from model import get_openai_model
from model import get_openai_model_settings

from agents import Agent
from agents import Runner
from agents.mcp import MCPServerStdio
from dotenv import load_dotenv

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Configuration:
    """Manages configuration and environment variables for the MCP Slackbot."""

    def __init__(self) -> None:
        """Initialize configuration with environment variables."""
        self.load_env()
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_app_token = os.getenv("SLACK_APP_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.http_proxy = os.getenv("HTTP_PROXY")

    @staticmethod
    def load_env() -> None:
        """Load environment variables from .env file."""
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> Dict[str, Any]:
        """Load server configuration from JSON file.

        Args:
            file_path: Path to the JSON configuration file.

        Returns:
            Dict containing server configuration.

        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            JSONDecodeError: If configuration file is invalid JSON.
        """
        with open(file_path, "r") as f:
            return json.load(f)


class OpenAIAgent:
    """A wrapper for OpenAI Agent"""

    def __init__(self, name: str, agent: Agent) -> None:
        self.current_agent = agent
        self.name = name

    @classmethod
    def from_json(cls, name: str, config: Dict[str, Any]) -> OpenAIAgent:
        agent = Agent(
            name=name,
            instructions="You are a helpful Slack bot assistant. When responding, you must strictly use Slack’s mrkdwn formatting syntax only. Do not generate headings (#), tables, or any other Markdown features not supported by Slack. Ensure that all output strictly complies with Slack’s mrkdwn specifications.",
            model=get_openai_model(),
            model_settings=get_openai_model_settings(),
            mcp_servers=[
                MCPServerStdio(
                    params={
                        "command": srv_config["command"],
                        "args": srv_config["args"],
                    }
                )
                for _, srv_config in config
            ],
        )
        return cls(name, agent)

    async def connect(self) -> None:
        for mcp_server in self.current_agent.mcp_servers:
            try:
                await mcp_server.connect()
                logging.info(f"Server {mcp_server.name} connecting")
            except Exception as e:
                logging.error(
                    f"Error during connecting of server {mcp_server.name}: {e}"
                )

    async def run(self, messages: List) -> str:
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


class SlackMCPBot:
    """Manages the Slack bot integration with agents."""

    def __init__(
        self,
        slack_bot_token: str,
        slack_app_token: str,
        proxy: str,
        openai_agent: OpenAIAgent,
    ) -> None:
        self.app = AsyncApp(token=slack_bot_token)
        # Create a socket mode handler with the app token
        self.socket_mode_handler = AsyncSocketModeHandler(self.app, slack_app_token)

        self.client = AsyncWebClient(token=slack_bot_token, proxy=proxy)
        self.agent = openai_agent
        self.conversations = {}  # Store conversation context per channel

        # Set up event handlers
        self.app.event("app_mention")(self.handle_mention)
        self.app.message()(self.handle_message)

    async def initialize_agent(self) -> None:
        """Initialize all MCP servers and discover tools."""
        try:
            await self.agent.connect()
            logging.info(f"Initialized agent {self.agent.name} with tools")
        except Exception as e:
            logging.error(f"Failed to initialize agent {self.agent.name}: {e}")

    async def initialize_bot_info(self) -> None:
        """Get the bot's ID and other info."""
        try:
            auth_info = await self.client.auth_test()
            self.bot_id = auth_info["user_id"]
            logging.info(f"Bot initialized with ID: {self.bot_id}")
        except Exception as e:
            logging.error(f"Failed to get bot info: {e}")
            self.bot_id = None

    async def handle_mention(self, event, say):
        """Handle mentions of the bot in channels."""
        await self._process_message(event, say)

    async def handle_message(self, message, say):
        """Handle direct messages to the bot."""
        await self._process_message(message, say)
        # Only process direct messages
        # if message.get("channel_type") == "im" and not message.get("subtype"):

    async def _process_message(self, event, say):
        """Process incoming messages and generate responses."""
        channel = event["channel"]
        user_id = event.get("user")

        # Skip messages from the bot itself
        if user_id == getattr(self, "bot_id", None):
            return

        # Get text and remove bot mention if present
        text = event.get("text", "")
        if hasattr(self, "bot_id") and self.bot_id:
            text = text.replace(f"<@{self.bot_id}>", "").strip()

        thread_ts = event.get("thread_ts", event.get("ts"))

        # Get or create conversation context
        if channel not in self.conversations:
            self.conversations[channel] = {"messages": []}

        try:
            messages = []

            # Add user message to history
            self.conversations[channel]["messages"].append(
                {"role": "user", "content": text}
            )

            # Add conversation history (last 5 messages)
            if "messages" in self.conversations[channel]:
                messages.extend(self.conversations[channel]["messages"][-5:])

            logger.info(messages)
            # Get LLM response
            agent_resp = await self.agent.run(messages)

            # Add assistant response to conversation history
            self.conversations[channel]["messages"].append(
                {"role": "assistant", "content": agent_resp}
            )

            # Send the response to the user
            await say(text=agent_resp, channel=channel, thread_ts=thread_ts)

        except Exception as e:
            error_message = f"I'm sorry, I encountered an error: {str(e)}"
            logging.error(f"Error processing message: {e}", exc_info=True)
            await say(text=error_message, channel=channel, thread_ts=thread_ts)

    async def start(self) -> None:
        """Start the Slack bot."""
        # await self.connect()
        await self.initialize_agent()
        await self.initialize_bot_info()
        # Start the socket mode handler
        logging.info("Starting Slack bot...")
        asyncio.create_task(self.socket_mode_handler.start_async())
        logging.info("Slack bot started and waiting for messages")

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, "socket_mode_handler"):
                await self.socket_mode_handler.close_async()
            logging.info("Slack socket mode handler closed")
        except Exception as e:
            logging.error(f"Error closing socket mode handler: {e}")


async def main() -> None:
    """Initialize and run the Slack bot."""
    config = Configuration()

    server_config = config.load_config("servers_config.json")
    print(server_config["mcpServers"].items())

    # Initialize the OpenAI agents
    openai_agent = OpenAIAgent.from_json(
        "Slack Bot Agent", server_config["mcpServers"].items()
    )

    slack_bot = SlackMCPBot(
        config.slack_bot_token,
        config.slack_app_token,
        config.http_proxy,
        openai_agent,
    )

    try:
        await slack_bot.start()
        # Keep the main task alive until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        await slack_bot.cleanup()
        await openai_agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
