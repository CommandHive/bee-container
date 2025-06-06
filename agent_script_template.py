#!/usr/bin/env python3
"""
Dynamically generated agent script for user {{ user_address }}.
Generated from configuration.
"""

import asyncio
import json
from typing import Dict, List
from rich import print as rich_print
import os
from mcp_agent.core.fastagent import FastAgent
from dotenv import load_dotenv
import redis.asyncio as aioredis

load_dotenv()

# Agent configuration
subagents_config = {{ subagents_config | tojson }}
sample_json_config = {{ sample_json_config | tojson }}

# Create FastAgent instance
fast = FastAgent(
    name="{{ agent_name }}",
    json_config=sample_json_config,
    parse_cli_args=False
)

# Create agents from configuration
def create_agents_from_config(config_list: List[Dict]) -> List[str]:
    """Create agents dynamically from JSON configuration."""
    agent_names = []
    
    for agent_config in config_list:
        name = agent_config.get("name")
        instruction = agent_config.get("instruction", "")
        servers = agent_config.get("servers", [])
        model = agent_config.get("model", "haiku")
        
        if not name:
            rich_print(f"[red]Warning: Agent config missing name, skipping: {agent_config}[/red]")
            continue
            
        # Create agent decorator kwargs
        agent_kwargs = {
            "name": name,
            "instruction": instruction,
            "servers": servers,
            "model": model
        }
            
        # Create the agent using the decorator
        @fast.agent(**agent_kwargs)
        def agent_function():
            """Dynamically created agent function"""
            pass
            
        agent_names.append(name)
        rich_print(f"[green]Created agent: {name}[/green]")
    
    return agent_names

# Create agents from configuration
created_agent_names = create_agents_from_config(subagents_config)

# Create orchestrator with the dynamically created agents
@fast.orchestrator(
    name="{{ orchestrator_name }}",
    agents=created_agent_names,
    plan_type="full",
    model="haiku"
)
async def orchestrate_task():
    """Orchestrator function"""
    pass

async def main():
    """Main agent runner with Redis pub/sub."""
    rich_print("Starting agent for user {{ user_address }}...")
    rich_print(f"[blue]Created agents: {created_agent_names}[/blue]")
    
    # Create Redis client
    redis_client = aioredis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )
    
    # Register agents and keep it running
    async with fast.run() as agent:        
        try:
            # Subscribe to the input channel
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("agent:{{ redis_channel }}")
            
            {% if polling_enabled %}
            # Start periodic polling if configured
            polling_interval = {{ polling_interval }}
            polling_prompt = """{{ polling_prompt }}"""
            
            async def periodic_polling():
                while True:
                    try:
                        await asyncio.sleep(polling_interval)
                        rich_print("[cyan]Running periodic polling task...[/cyan]")
                        result = await agent.orchestrate(polling_prompt)
                        rich_print(f"[green]Polling result:[/green] {result}")
                    except Exception as e:
                        rich_print(f"[red]Polling error:[/red] {e}")
            
            # Start polling task
            polling_task = asyncio.create_task(periodic_polling())
            {% endif %}
            
            # Initial task if provided
            {% if initial_task %}
            initial_task = """{{ initial_task }}"""
            rich_print("[cyan]Running initial task...[/cyan]")
            await agent.orchestrate(initial_task)
            rich_print("[green]Initial task completed![/green]")
            {% endif %}
            
            # Keep running and listen for Redis messages
            rich_print("[yellow]Listening for Redis messages on channel 'agent:{{ redis_channel }}'...[/yellow]")
            while True:
                # Process Redis messages directly
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message and message.get('type') == 'message':
                    try:
                        # Process the message data
                        data = message.get('data')
                        if isinstance(data, bytes):
                            data = data.decode('utf-8')
                        
                        # Try to parse JSON
                        try:
                            data_obj = json.loads(data)
                            
                            # If this is a user message, extract content and send to orchestrator
                            if data_obj.get('type') == 'user' and 'content' in data_obj:
                                user_input = data_obj['content']
                                rich_print(f"[blue]Received user input:[/blue] {user_input}")
                                
                                # Send to orchestrator
                                response = await agent.orchestrate(user_input)
                                rich_print(f"[green]Orchestrator response:[/green] {response}")
                                
                        except json.JSONDecodeError:
                            rich_print(f"[red]Received non-JSON message:[/red] {data}")
                            # Try to process as plain text
                            response = await agent.orchestrate(data)
                            rich_print(f"[green]Orchestrator response:[/green] {response}")
                            
                    except Exception as e:
                        rich_print(f"[bold red]Error processing Redis message:[/bold red] {e}")
                        import traceback
                        rich_print(f"[dim red]{traceback.format_exc()}[/dim red]")
                
                # Small delay to prevent CPU spike
                await asyncio.sleep(0.05)
                
        except asyncio.CancelledError:
            rich_print("[yellow]Agent was cancelled[/yellow]")
        except KeyboardInterrupt:
            rich_print("[yellow]Agent stopped by user[/yellow]")
        finally:
            {% if polling_enabled %}
            # Cancel polling task
            if 'polling_task' in locals():
                polling_task.cancel()
            {% endif %}
            # Clean up Redis connection
            if 'pubsub' in locals():
                await pubsub.unsubscribe("agent:{{ redis_channel }}")
            await redis_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        rich_print("\n[yellow]Agent stopped by user[/yellow]")