# Agent Manager API

A FastAPI-based system for managing AI agents in Docker containers with dynamic creation, lifecycle management, and background execution.

## Features

- **Create agents** dynamically from JSON configuration
- **Start/Stop agents** using supervisord
- **Delete agents** and cleanup resources
- **List agents** with status information
- **Background execution** with Redis pub/sub integration

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agents` | Create a new agent |
| GET | `/agents` | List all agents |
| GET | `/agents/{name}` | Get agent details |
| POST | `/agents/{name}/start` | Start an agent |
| POST | `/agents/{name}/stop` | Stop an agent |
| DELETE | `/agents/{name}` | Delete an agent |
| GET | `/health` | Health check |

## Quick Start

### 1. Build and Run Container

```bash
docker build -t agent-manager .
docker run -p 8080:8080 -p 6379:6379 agent-manager
```

### 2. API Documentation

Visit `http://localhost:8080/docs` for interactive API documentation.

## Testing the API

### Create an Agent

```bash
curl -X POST "http://localhost:8080/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "crypto_trader",
    "subagents": [
      {
        "name": "price_finder",
        "instruction": "Find cryptocurrency prices using web search",
        "servers": ["fetch", "brave"],
        "model": "haiku"
      },
      {
        "name": "analyzer",
        "instruction": "Analyze price data and provide trading recommendations",
        "servers": [],
        "model": "haiku"
      }
    ],
    "json_config": {
      "mcp": {
        "servers": {
          "fetch": {
            "name": "fetch",
            "description": "Web fetching server",
            "transport": "stdio",
            "command": "uvx",
            "args": ["mcp-server-fetch"]
          },
          "brave": {
            "name": "brave",
            "description": "Brave search server",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-brave-search"],
            "env": {
              "BRAVE_API_KEY": ""
            }
          }
        }
      },
      "default_model": "haiku",
      "logger": {
        "level": "info",
        "type": "console"
      },
      "pubsub_enabled": true,
      "pubsub_config": {
        "backend": "redis",
        "channel_name": "crypto_trader"
      },
      "anthropic": {
        "api_key": ""
      }
    },
    "initial_task": "Monitor Bitcoin price and alert if it changes by more than 5%"
  }'
```

### List All Agents

```bash
curl "http://localhost:8080/agents"
```

### Start an Agent

```bash
curl -X POST "http://localhost:8080/agents/crypto_trader/start"
```

### Stop an Agent

```bash
curl -X POST "http://localhost:8080/agents/crypto_trader/stop"
```

### Get Agent Status

```bash
curl "http://localhost:8080/agents/crypto_trader"
```

### Delete an Agent

```bash
curl -X DELETE "http://localhost:8080/agents/crypto_trader"
```

## Interacting with Agents

Once an agent is running, you can send messages via Redis:

```bash
# Connect to Redis
redis-cli

# Send a message to the agent
PUBLISH agent:crypto_trader '{"type": "user", "content": "What is the current Bitcoin price?", "channel_id": "agent:crypto_trader", "metadata": {"model": "claude-3-5-haiku-latest", "name": "default"}}'
```

## Agent Configuration Structure

### SubAgent
```json
{
  "name": "agent_name",
  "instruction": "What this agent should do",
  "servers": ["list", "of", "mcp_servers"],
  "model": "haiku"
}
```

### JSON Config
The `json_config` follows the MCP (Model Context Protocol) specification and includes:
- **mcp.servers**: MCP server configurations
- **default_model**: Default model to use
- **logger**: Logging configuration
- **pubsub_config**: Pub/sub backend configuration
- **anthropic**: Claude API configuration

## File Structure

```
/app/
├── agent_manager.py          # FastAPI server
├── agents/                   # Generated agent files
│   └── {name}_agent.py
├── logs/                     # Log files
└── /etc/supervisor/conf.d/
    └── agents/               # Supervisor configs
        └── {name}.conf
```

## Environment Variables

Set these in your `.env` file or environment:

```bash
CLAUDE_API_KEY=your_claude_api_key
BRAVE_API_KEY=your_brave_search_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

## Logs

View agent logs:
```bash
# Agent Manager logs
tail -f /var/log/supervisor/agent_manager.out.log

# Individual agent logs
tail -f /var/log/supervisor/{agent_name}_agent.out.log
```

## Troubleshooting

### Agent Won't Start
1. Check supervisor logs: `supervisorctl tail {agent_name}_agent`
2. Verify agent file exists: `ls /app/agents/`
3. Check API keys in environment

### Redis Connection Issues
1. Verify Redis is running: `redis-cli ping`
2. Check Redis logs: `tail -f /var/log/supervisor/redis.out.log`

### API Not Responding
1. Check agent manager logs: `supervisorctl tail agent_manager`
2. Verify port 8080 is exposed and accessible

## Development

To modify the API:
1. Edit `agent_manager.py`
2. Restart the container or supervisor service:
   ```bash
   supervisorctl restart agent_manager
   ```

## Security Notes

- Agents run as `agentuser` (non-root)
- API keys should be properly secured
- Consider network isolation in production
- Monitor agent resource usage