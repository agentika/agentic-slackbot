import logging
import asyncio

from bot.slack import SlackMCPBot
from bot.agent import OpenAIAgent
from bot.config import Configuration


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    """Initialize and run the Slack bot."""
    config = Configuration()

    server_config = config.load_config("servers_config.json")

    # Initialize the OpenAI agents with mcp servers
    openai_agent = OpenAIAgent.from_dict("Slack Bot Agent", server_config["mcpServers"])

    # Initialize the OpenAI agents
    # openai_agent = OpenAIAgent("Slack Bot Agent")

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
