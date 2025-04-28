# agentic-slackbot
A simple Slack bot that uses the OpenAI Agents SDK to interact with the Model Context Protocol (MCP) server.

## Install Dependencies

```bash
uv sync
```


## Environment Variables

Create a `.envrc` file in the root directory of the project and add the following environment variables:

```
export OPENAI_API_KEY=""
export SLACK_BOT_TOKEN=""
export SLACK_APP_TOKEN=""
export OPENAI_MODEL="gpt-4o"
export HTTP_PROXY=""
```

## Running the Bot

```bash
uv run app.py
``````

## Credit

This project is based on the [sooperset/mcp-client-slackbot](https://github.com/sooperset/mcp-client-slackbot) example.
