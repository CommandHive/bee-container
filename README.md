# Agent Manager API

A FastAPI-based system for managing AI agents in Docker containers with dynamic creation, lifecycle management, and MSK/Kafka message processing. This system creates agents from configurable templates and manages their execution using supervisord.

## How to use it?

  1. Start server independently:
  `python agent_manager.py` 
  or
  `uv run agent_manager.py`

  2. Start docker container:
  # Build the image first
  `docker build -t agent-manager .`

  # Run the container
  for mks / kafka
  `docker run -p 8080:8080 agent-manager`
  
  for redis
  `docker run -p 8080:8080 -p 6379:6379 agent-manager`


## Features

- **Create agents** dynamically from JSON configuration using templates
- **Multi-user support** with isolated agent directories per user
- **Start/Stop agents** using supervisord process management
- **Delete agents** and cleanup resources automatically
- **List agents** with real-time status information
- **MSK/Kafka integration** for scalable message processing
- **Template-based agent generation** from `agent_script_template.py`

## API Endpoints

| Method | Endpoint | Description | Query Parameters |
|--------|----------|-------------|------------------|
| POST | `/agents` | Create a new agent | - |
| GET | `/agents` | List all agents | `username` (optional) - filter by user |
| GET | `/agents/{agent_name}` | Get agent details | `username` (required) |
| POST | `/agents/{agent_name}/start` | Start an agent | `username` (required) |
| POST | `/agents/{agent_name}/stop` | Stop an agent | `username` (required) |
| DELETE | `/agents/{agent_name}` | Delete an agent | `username` (required) |
| GET | `/health` | Health check | - |

## Quick Start

### 1. Build and Run Container

```bash
# Build the image
docker build -t agent-manager .

# Run with MSK/Kafka (recommended)
docker run -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_REGION=ap-south-1 \
  -e CLAUDE_API_KEY=your_claude_key \
  agent-manager

# Or run with Redis (legacy)
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
    "username": "alice",
    "name": "crypto_trader",
    "subagents": [
      {
        "name": "finder",
        "instruction": "You are an agent with access to the internet; you need to search about the latest prices of Bitcoin and other major cryptocurrencies and report back.",
        "servers": ["fetch"],
        "model": "haiku"
      },
      {
        "name": "reporter",
        "instruction": "You are an agent that takes the raw pricing data provided by the finder agent and produces a concise, human-readable summary highlighting current prices, 24-hour changes, and key market insights.",
        "servers": [],
        "model": "haiku"
      }
    ],
    "json_config": {
      "mcp": {
        "servers": {
          "fetch": {
            "name": "fetch",
            "description": "A server for fetching links",
            "transport": "stdio",
            "command": "uvx",
            "args": ["mcp-server-fetch"],
            "tool_calls": [
              {
                "name": "fetch",
                "seek_confirm": true,
                "time_to_confirm": 120000,
                "default": "reject"
              }
            ]
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
        "backend": "msk",
        "channel_name": "crypto_trader",
        "msk": {
          "bootstrap_servers": [
            "b-3-public.commandhive.aewd11.c4.kafka.ap-south-1.amazonaws.com:9198",
            "b-1-public.commandhive.aewd11.c4.kafka.ap-south-1.amazonaws.com:9198",
            "b-2-public.commandhive.aewd11.c4.kafka.ap-south-1.amazonaws.com:9198"
          ],
          "aws_region": "ap-south-1",
          "topic_prefix": "mcp_agent_",
          "security_protocol": "SASL_SSL",
          "sasl_mechanism": "OAUTHBEARER",
          "ssl_config": {
            "check_hostname": false,
            "verify_mode": "none"
          },
          "producer_config": {
            "acks": "all",
            "client_id": "mcp_agent_producer"
          },
          "consumer_config": {
            "auto_offset_reset": "latest",
            "enable_auto_commit": true,
            "client_id": "mcp_agent_consumer"
          }
        }
      },
      "anthropic": {
        "api_key": ""
      }
    },
    "initial_task": "Find the current price of Bitcoin and provide a market summary."
  }'
```

### List All Agents

```bash
# List all agents
curl "http://localhost:8080/agents"

# List agents for specific user
curl "http://localhost:8080/agents?username=alice"
```

### Start an Agent

```bash
curl -X POST "http://localhost:8080/agents/crypto_trader/start?username=alice"
```

### Stop an Agent

```bash
curl -X POST "http://localhost:8080/agents/crypto_trader/stop?username=alice"
```

### Get Agent Status

```bash
curl "http://localhost:8080/agents/crypto_trader?username=alice"
```

### Delete an Agent

```bash
curl -X DELETE "http://localhost:8080/agents/crypto_trader?username=alice"
```

## Interacting with Agents

Once an agent is running, you can send messages via MSK/Kafka using the provided producer script:

```bash
# Using the MSK producer script
python msk_producer.py

# The producer will send messages to the topic: mcp_agent_crypto_trader
# Message format:
{
  "type": "user",
  "content": "What is the current Bitcoin price?",
  "channel_id": "agent:crypto_trader",
  "metadata": {
    "model": "claude-3-5-haiku-latest",
    "name": "default"
  }
}
```

### Alternative: Redis (Legacy Support)

For Redis-based agents (if configured):

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

### AgentConfig Model
```json
{
  "username": "string",           // Required: User identifier for multi-tenancy
  "name": "string",              // Required: Agent name (unique per user)
  "subagents": [SubAgent],        // Required: List of sub-agents
  "json_config": {},              // Required: MCP configuration
  "initial_task": "string"       // Optional: Task to run on startup
}
```

### JSON Config Structure
The `json_config` follows the MCP (Model Context Protocol) specification and includes:
- **mcp.servers**: MCP server configurations with tool confirmation settings
- **default_model**: Default model to use (e.g., "haiku")
- **logger**: Logging configuration (level, type)
- **pubsub_enabled**: Enable pub/sub messaging (boolean)
- **pubsub_config**: Message backend configuration (MSK/Kafka or Redis)
  - **backend**: "msk" or "redis"
  - **channel_name**: Channel/topic name for messaging
  - **msk**: MSK-specific configuration (bootstrap servers, region, etc.)
- **anthropic**: Claude API configuration

## File Structure

```
/app/
├── agent_manager.py              # FastAPI server
├── agent_script_template.py      # Template for generating agents
├── sample_queen_agent.py         # Example agent implementation
├── msk_producer.py              # MSK message producer utility
├── msk_consumer.py              # MSK message consumer utility
├── agents/                      # User-specific agent directories
│   └── {username}/
│       ├── agents/              # Generated agent files
│       │   └── {name}_agent.py
│       └── supervisor/          # Supervisor configs
│           └── {name}.ini
└── logs/                        # Log files
```

## Agent Template System

Agents are generated from `agent_script_template.py` using placeholder replacement:

- **PLACEHOLDER_SUBAGENTS_CONFIG**: Replaced with actual subagents configuration
- **PLACEHOLDER_JSON_CONFIG**: Replaced with MCP configuration
- **PLACEHOLDER_AGENT_NAME**: Replaced with agent name
- **PLACEHOLDER_INITIAL_TASK**: Replaced with initial task (if provided)
- **PLACEHOLDER_INITIAL_TASK_EXECUTION**: Replaced with task execution code

## Environment Variables

Set these in your `.env` file or environment:

```bash
# Required for Claude API
CLAUDE_API_KEY=your_claude_api_key

# Required for MSK/Kafka (recommended)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=ap-south-1

# Optional for Redis (legacy support)
REDIS_HOST=localhost
REDIS_PORT=6379

# Optional for additional MCP servers
BRAVE_API_KEY=your_brave_search_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

## Logs

View agent logs:
```bash
# Agent Manager logs
tail -f /var/log/supervisor/agent_manager.out.log

# Individual agent logs (per user)
tail -f /app/agents/{username}/all.log

# Supervisor status
supervisorctl status

# View specific agent logs via supervisorctl
supervisorctl tail {username}_{agent_name}_agent
```

## Troubleshooting

### Agent Won't Start
1. Check supervisor logs: `supervisorctl tail {username}_{agent_name}_agent`
2. Verify agent file exists: `ls /app/agents/{username}/agents/`
3. Check supervisor config: `ls /app/agents/{username}/supervisor/`
4. Verify API keys in environment
5. Check supervisor configuration: `supervisorctl reread && supervisorctl update`

### MSK/Kafka Connection Issues
1. Verify AWS credentials are set correctly
2. Check MSK cluster accessibility and security groups
3. Test MSK connection: `python msk_producer.py`
4. Verify topic exists: `mcp_agent_{channel_name}`

### Redis Connection Issues (Legacy)
1. Verify Redis is running: `redis-cli ping`
2. Check Redis logs: `tail -f /var/log/supervisor/redis.out.log`

### API Not Responding
1. Check agent manager logs: `supervisorctl tail agent_manager`
2. Verify port 8080 is exposed and accessible
3. Test health endpoint: `curl http://localhost:8080/health`

### Template Issues
1. Verify `agent_script_template.py` exists and is valid
2. Check placeholder replacement in generated agents
3. Compare generated agent with `sample_queen_agent.py`

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