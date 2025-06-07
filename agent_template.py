import asyncio
import json
from typing import Dict, List
import os
from mcp_agent.core.fastagent import FastAgent
from dotenv import load_dotenv
load_dotenv()
import redis.asyncio as aioredis

# PLACEHOLDER_SUBAGENTS_CONFIG - This will be replaced with actual subagents configuration
subagents_config = []

# PLACEHOLDER_JSON_CONFIG - This will be replaced with actual JSON configuration
sample_json_config = {}

# Create FastAgent instance
fast = FastAgent(
    name="PLACEHOLDER_AGENT_NAME",  # This will be replaced with actual agent name
    json_config=sample_json_config,
    parse_cli_args=False
)

# Dynamically create agents from JSON configuration using a for loop
def create_agents_from_config(config_list: List[Dict]) -> List[str]:
    """
    Create agents dynamically from JSON configuration.
    Returns a list of agent names for use in the orchestrator.
    """
    agent_names = []
    
    for agent_config in config_list:
        name = agent_config.get("name")
        instruction = agent_config.get("instruction", "")
        servers = agent_config.get("servers", [])
        model = agent_config.get("model", None)
        
        if not name:
            continue
            
        # Create agent decorator kwargs
        agent_kwargs = {
            "name": name,
            "instruction": instruction,
            "servers": servers
        }
        
        # Add model if specified
        if model:
            agent_kwargs["model"] = model
            
        # Create the agent using the decorator
        @fast.agent(**agent_kwargs)
        def agent_function():
            """Dynamically created agent function"""
            pass
            
        agent_names.append(name)
    
    return agent_names

# Create agents from configuration
created_agent_names = create_agents_from_config(subagents_config)

# Create orchestrator with the dynamically created agents
@fast.orchestrator(
    name="orchestrate", 
    agents=created_agent_names,  # Use the list of created agent names
    plan_type="full",
    model="haiku"
)
async def orchestrate_task():
    """Orchestrator function"""
    pass

async def main():
    """Test initializing FastAgent with JSON config in interactive mode."""
    
    # Create Redis client
    redis_client = aioredis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True
    )
    
    # Register agents and keep it running
    async with fast.run() as agent:        
        try:
            # Subscribe to the input channel
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("agent:PLACEHOLDER_AGENT_NAME")
            
            # PLACEHOLDER_INITIAL_TASK - This will be replaced with initial task if provided
            # PLACEHOLDER_INITIAL_TASK_EXECUTION - This will be replaced with task execution if provided
            
            # Keep running and listen for Redis messages
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
                                
                                # Send to orchestrator instead of individual agent
                                response = await agent.orchestrate(user_input)
                                
                        except json.JSONDecodeError:
                            # Try to process as plain text
                            response = await agent.orchestrate(data)
                            
                    except Exception as e:
                        import traceback
                
                # Small delay to prevent CPU spike
                await asyncio.sleep(0.05)
                
        finally:
            # Clean up Redis connection
            if 'pubsub' in locals():
                await pubsub.unsubscribe("agent:PLACEHOLDER_AGENT_NAME")
            await redis_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass