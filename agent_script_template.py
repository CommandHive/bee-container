import asyncio
import json
from typing import Dict, List
import os
from  mcp_agent.core.fastagent import FastAgent
from dotenv import load_dotenv
load_dotenv()
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.abc import AbstractTokenProvider
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider
import ssl
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_ssl_context():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.options |= ssl.OP_NO_SSLv2
    ssl_context.options |= ssl.OP_NO_SSLv3
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    ssl_context.load_default_certs()
    return ssl_context

class AWSTokenProvider(AbstractTokenProvider):
    def __init__(self, region="ap-south-1"):
        self.region = region
    
    async def token(self):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._generate_token)
    
    def _generate_token(self):
        try:
            token, _ = MSKAuthTokenProvider.generate_auth_token(self.region)
            return token
        except Exception as e:
            logger.error(f"Failed to generate auth token: {e}")
            raise

async def create_msk_consumer(bootstrap_servers, topic_name, consumer_group="mcp_agent_consumer"):
    try:
        tp = AWSTokenProvider()
        consumer = AIOKafkaConsumer(
            topic_name,
            bootstrap_servers=bootstrap_servers,
            group_id=consumer_group,
            security_protocol='SASL_SSL',
            ssl_context=create_ssl_context(),
            sasl_mechanism='OAUTHBEARER',
            sasl_oauth_token_provider=tp,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            client_id='mcp_agent_consumer',
            api_version="0.11.5",
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000
        )
        
        await consumer.start()
        logger.info(f"MSK consumer created successfully for topic '{topic_name}'!")
        return consumer
        
    except Exception as e:
        logger.error(f"Failed to create MSK consumer: {str(e)}")
        return None

async def ensure_topic_exists(bootstrap_servers, topic_name, num_partitions=1, replication_factor=1):
    """Ensure Kafka topic exists, create if it doesn't"""
    try:
        tp = AWSTokenProvider()
        admin_client = AIOKafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            security_protocol='SASL_SSL',
            ssl_context=create_ssl_context(),
            sasl_mechanism='OAUTHBEARER',
            sasl_oauth_token_provider=tp,
            client_id=f'admin_client_{topic_name}'
        )
        
        await admin_client.start()
        
        try:
            # Try to create the topic
            new_topic = NewTopic(
                name=topic_name,
                num_partitions=num_partitions,
                replication_factor=replication_factor
            )
            
            result = await admin_client.create_topics([new_topic])
            logger.info(f"Topic '{topic_name}' created successfully")
            
        except TopicAlreadyExistsError:
            logger.info(f"Topic '{topic_name}' already exists")
        except Exception as e:
            logger.warning(f"Error creating topic '{topic_name}': {e}")
            
    except Exception as e:
        logger.error(f"Failed to connect to Kafka admin client: {e}")
    finally:
        try:
            await admin_client.close()
        except:
            pass

# PLACEHOLDER_SUBAGENTS_CONFIG - This will be replaced with actual subagents configuration
subagents_config = []

# PLACEHOLDER_JSON_CONFIG - This will be replaced with actual JSON configuration
sample_json_config = {}

# Create FastAgent instance
fast = FastAgent(
    name="PLACEHOLDER_AGENT_NAME",
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
    """Test initializing FastAgent with JSON config using MSK for message consumption."""
    
    # MSK configuration from the FastAgent config
    msk_config = sample_json_config["pubsub_config"]["msk"]
    bootstrap_servers = msk_config["bootstrap_servers"]
    topic_name = msk_config["topic_prefix"] + sample_json_config["pubsub_config"]["channel_name"]
    
    # Ensure topic exists before creating consumer
    await ensure_topic_exists(bootstrap_servers, topic_name)
    
    # Create MSK consumer
    consumer = await create_msk_consumer(bootstrap_servers, topic_name)
    if not consumer:
        logger.error("Failed to create MSK consumer. Exiting.")
        return
    
    # Register agents and keep it running
    async with fast.run() as agent:        
        try:
            # PLACEHOLDER_INITIAL_TASK - This will be replaced with initial task if provided
            # PLACEHOLDER_INITIAL_TASK_EXECUTION - This will be replaced with task execution if provided
            
            # Keep running and listen for MSK messages
            logger.info("Starting to listen for MSK messages...")
            async for message in consumer:
                try:
                    # Process the message data
                    if message.value:
                        logger.info(f"Received message: {message.value}")
                        
                        # If this is a user message, extract content and send to orchestrator
                        if isinstance(message.value, dict) and message.value.get('type') == 'user' and 'content' in message.value:
                            user_input = message.value['content']
                            logger.info(f"Processing user input: {user_input}")
                            
                            # Send to orchestrator instead of individual agent
                            response = await agent.orchestrate(user_input)
                            
                        elif isinstance(message.value, str):
                            # Try to parse as JSON first
                            try:
                                data_obj = json.loads(message.value)
                                if data_obj.get('type') == 'user' and 'content' in data_obj:
                                    user_input = data_obj['content']
                                    logger.info(f"Processing user input from JSON: {user_input}")
                                    response = await agent.orchestrate(user_input)
                                else:
                                    # Process as plain text
                                    response = await agent.orchestrate(message.value)
                            except json.JSONDecodeError:
                                # Process as plain text
                                response = await agent.orchestrate(message.value)
                                
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    import traceback
                    traceback.print_exc()
                
        finally:
            # Clean up MSK consumer
            logger.info("Stopping MSK consumer...")
            await consumer.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass