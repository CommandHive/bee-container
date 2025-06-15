import asyncio
import json
import os
import subprocess
from typing import Dict, List, Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis.asyncio as aioredis

app = FastAPI(title="Agent Manager API", version="1.0.0")

print(Path)
ABSOLUTE_PATH = "/Users/vaibhavgeek/commandhive/docker-container"
AGENTS_BASE_DIR = Path(ABSOLUTE_PATH) / "agents"
MAIN_DIRECTORY = Path(ABSOLUTE_PATH)

class SubAgent(BaseModel):
    name: str
    instruction: str
    servers: List[str] = []
    model: str = "haiku"

class AgentConfig(BaseModel):
    username: str
    name: str
    subagents: List[SubAgent]
    json_config: Dict
    initial_task: Optional[str] = None

class AgentStatus(BaseModel):
    name: str
    status: str
    pid: Optional[int] = None

class AgentManager:
    def __init__(self):
        AGENTS_BASE_DIR.mkdir(exist_ok=True)
        
    def _get_user_directories(self, username: str):
        """Get user-specific directories, creating them if they don't exist"""
        user_dir = AGENTS_BASE_DIR / username
        agents_dir = user_dir / "agents"
        supervisor_dir = user_dir / "supervisor"
        
        # Create directories if they don't exist
        user_dir.mkdir(exist_ok=True)
        agents_dir.mkdir(exist_ok=True)
        supervisor_dir.mkdir(exist_ok=True)
        
        return agents_dir, supervisor_dir
        
    async def create_agent(self, config: AgentConfig) -> Dict:
        """Create a new agent with the given configuration"""
        agents_dir, supervisor_dir = self._get_user_directories(config.username)
        agent_file = agents_dir / f"{config.name}_agent.py"
        
        if agent_file.exists():
            raise HTTPException(status_code=400, detail=f"Agent '{config.name}' already exists for user '{config.username}'")
        
        agent_code = self._generate_agent_code(config)
        agent_file.write_text(agent_code)
        
        supervisor_config = self._generate_supervisor_config(config.name, config.username)
        supervisor_file = supervisor_dir / f"{config.name}.ini"
        supervisor_file.write_text(supervisor_config)
        
        return {"message": f"Agent '{config.name}' created successfully for user '{config.username}'", "file": str(agent_file)}
    
    def _generate_agent_code(self, config: AgentConfig) -> str:
        """Generate Python agent code from template file"""
        template_path = Path(ABSOLUTE_PATH) / "agent_script_template.py"
        
        if not template_path.exists():
            raise HTTPException(status_code=500, detail="Agent template file not found")
        
        # Read the template file
        template_content = template_path.read_text()
        
        # Replace placeholders with actual values
        # Convert JSON to Python-compatible format (true/false -> True/False)
        subagents_json = json.dumps([agent.dict() for agent in config.subagents], indent=4)
        subagents_python = subagents_json.replace('true', 'True').replace('false', 'False').replace('null', 'None')
        
        config_json = json.dumps(config.json_config, indent=4)
        config_python = config_json.replace('true', 'True').replace('false', 'False').replace('null', 'None')
        
        agent_code = template_content.replace(
            "# PLACEHOLDER_SUBAGENTS_CONFIG - This will be replaced with actual subagents configuration\nsubagents_config = []",
            f"subagents_config = {subagents_python}"
        ).replace(
            "# PLACEHOLDER_JSON_CONFIG - This will be replaced with actual JSON configuration\nsample_json_config = {}",
            f"sample_json_config = {config_python}"
        ).replace(
            "PLACEHOLDER_AGENT_NAME",
            config.name
        ).replace(
            'true', 'True'
        ).replace(
            'false', 'False'
        ).replace(
            'null', 'None'
        )
        
        # Handle initial task if provided
        if config.initial_task:
            initial_task_code = f'''
            # Initial task for the orchestrator
            initial_task = """{config.initial_task}"""
            await agent.orchestrate(initial_task)
            '''
            agent_code = agent_code.replace(
                "            # PLACEHOLDER_INITIAL_TASK - This will be replaced with initial task if provided\n            # PLACEHOLDER_INITIAL_TASK_EXECUTION - This will be replaced with task execution if provided",
                initial_task_code
            )
        else:
            agent_code = agent_code.replace(
                "            # PLACEHOLDER_INITIAL_TASK - This will be replaced with initial task if provided\n            # PLACEHOLDER_INITIAL_TASK_EXECUTION - This will be replaced with task execution if provided",
                ""
            )
        
        return agent_code
    
    def _generate_supervisor_config(self, agent_name: str, username: str) -> str:
        """Generate supervisord configuration for agent"""
        agents_dir, _ = self._get_user_directories(username)
        return f"""[program:{username}_{agent_name}_agent]
command=bash -c "source {ABSOLUTE_PATH}/.venv/bin/activate && python {agents_dir}/{agent_name}_agent.py"
directory={ABSOLUTE_PATH}
autostart=false
autorestart=true
stderr_logfile={agents_dir}/{agent_name}_logs.log
stdout_logfile={agents_dir}/{agent_name}_logs.log
user=vaibhavgeek
"""

    async def start_agent(self, agent_name: str, username: str) -> Dict:
        """Start an agent using supervisorctl"""
        try:
            agents_dir, supervisor_dir = self._get_user_directories(username)
            # Check if agent file exists first
            agent_file = agents_dir / f"{agent_name}_agent.py"
            print(agent_file)
            if not agent_file.exists():
                raise HTTPException(status_code=404, detail=f"Agent file '{agent_name}_agent.py' not found for user '{username}'")
            
            # Create log file if it doesn't exist
            log_file = agents_dir / f"{agent_name}_logs.log"
            if not log_file.exists():
                log_file.touch()
                print(f"Created log file: {log_file}")
            
            # Check if supervisor config exists
            supervisor_file = supervisor_dir / f"{agent_name}.ini"
            if not supervisor_file.exists():
                raise HTTPException(status_code=404, detail=f"Supervisor config '{agent_name}.ini' not found for user '{username}'")
            
            # First, make sure supervisor knows about the configuration
            print(f"Updating supervisor configuration for agent '{agent_name}'...")
            reread_result = subprocess.run(
                ["supervisorctl", "reread"], 
                capture_output=True, text=True, check=True
            )
            print(f"Reread output: {reread_result.stdout}")
            
            update_result = subprocess.run(
                ["supervisorctl", "update"], 
                capture_output=True, text=True, check=True
            )
            print(f"Update output: {update_result.stdout}")
            
            # Check if the program is now known to supervisor
            program_name = f"{username}_{agent_name}_agent"
            status_check = subprocess.run(
                ["supervisorctl", "status", program_name],
                capture_output=True, text=True
            )
            
            
            # Now try to start the agent
            print(f"Starting agent '{program_name}'...")
            start_result = subprocess.run(
                ["supervisorctl", "-c" , "/opt/homebrew/etc/supervisord.conf", "start", program_name],
                capture_output=True, text=True, check=True
            )
            
            print(f"Start output: {start_result.stdout}")
            
            # Verify the agent actually started
            final_status = subprocess.run(
                ["supervisorctl", "status", program_name],
                capture_output=True, text=True
            )
            
            return {
                "message": f"Agent '{agent_name}' started successfully for user '{username}'",
                "status": final_status.stdout.strip() if final_status.returncode == 0 else "unknown",
                "start_output": start_result.stdout.strip()
            }
            
        except subprocess.CalledProcessError as e:
            # Get more detailed error information
            error_details = {
                "command": " ".join(e.cmd) if e.cmd else "unknown",
                "return_code": e.returncode,
                "stdout": e.stdout.strip() if e.stdout else "",
                "stderr": e.stderr.strip() if e.stderr else ""
            }
            
            error_msg = f"Failed to start agent '{agent_name}' for user '{username}': Command '{error_details['command']}' "
            error_msg += f"returned non-zero exit status {error_details['return_code']}"
            
            if error_details['stderr']:
                error_msg += f". Error: {error_details['stderr']}"
            if error_details['stdout']:
                error_msg += f". Output: {error_details['stdout']}"
            
            # Additional diagnostic information
            try:
                # Check all supervisor programs
                all_status = subprocess.run(
                    ["supervisorctl", "status"],
                    capture_output=True, text=True
                )
                error_msg += f". All supervisor programs: {all_status.stdout}"
            except:
                pass
                
            raise HTTPException(status_code=500, detail=error_msg)
        
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        
        except Exception as e:
            # Handle any other unexpected errors
            raise HTTPException(
                status_code=500, 
                detail=f"Unexpected error starting agent '{agent_name}' for user '{username}': {str(e)}"
            )

    async def stop_agent(self, agent_name: str, username: str) -> Dict:
        """Stop an agent using supervisorctl"""
        try:
            program_name = f"{username}_{agent_name}_agent"
            result = subprocess.run(
                ["supervisorctl", "stop", program_name],
                capture_output=True, text=True, check=True
            )
            return {"message": f"Agent '{agent_name}' stopped successfully for user '{username}'"}
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop agent: {e.stderr}")

    async def delete_agent(self, agent_name: str, username: str) -> Dict:
        """Delete an agent and its configuration"""
        agents_dir, supervisor_dir = self._get_user_directories(username)
        agent_file = agents_dir / f"{agent_name}_agent.py"
        supervisor_file = supervisor_dir / f"{agent_name}.ini"
        
        await self.stop_agent(agent_name, username)
        
        if agent_file.exists():
            agent_file.unlink()
        if supervisor_file.exists():
            supervisor_file.unlink()
            
        subprocess.run(["supervisorctl", "reread"], check=True)
        subprocess.run(["supervisorctl", "update"], check=True)
        
        return {"message": f"Agent '{agent_name}' deleted successfully for user '{username}'"}

    async def list_agents(self, username: str = None) -> List[Dict]:
        """List all agents and their status for a specific user or all users"""
        agents = []
        
        # Get all running supervisor processes
        supervisor_agents = {}
        try:
            result = subprocess.run(
                ["supervisorctl", "status"],
                capture_output=True, text=True, check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if '_agent' in line and line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        program_name = parts[0]
                        # Extract username and agent name from program name (format: username_agentname_agent)
                        if program_name.count('_') >= 2:
                            name_parts = program_name.rsplit('_agent', 1)[0].split('_', 1)
                            if len(name_parts) == 2:
                                prog_username, agent_name = name_parts
                                # Filter by username if specified
                                if username is None or prog_username == username:
                                    status = parts[1]
                                    is_active = status.upper() in ['RUNNING']
                                    pid = None
                                    if len(parts) > 2 and parts[2].startswith('pid'):
                                        pid = int(parts[2].split()[1].rstrip(','))
                                    
                                    supervisor_agents[f"{prog_username}/{agent_name}"] = {
                                        "status": status,
                                        "is_active": is_active,
                                        "pid": pid
                                    }
        except subprocess.CalledProcessError:
            pass
        
        # Check file system for agent files
        if username:
            # Check specific user's agents
            agents_dir, _ = self._get_user_directories(username)
            if agents_dir.exists():
                for agent_file in agents_dir.glob("*_agent.py"):
                    agent_name = agent_file.stem.replace("_agent", "")
                    agent_key = f"{username}/{agent_name}"
                    
                    supervisor_info = supervisor_agents.get(agent_key, {
                        "status": "NOT_CONFIGURED",
                        "is_active": False,
                        "pid": None
                    })
                    
                    agents.append({
                        "agent": f"{username}/{agent_name}",
                        "file_exists": True,
                        "is_active_in_background": supervisor_info["is_active"],
                        "status": supervisor_info["status"],
                        "pid": supervisor_info["pid"]
                    })
        else:
            # Check all users' agents
            if AGENTS_BASE_DIR.exists():
                for user_dir in AGENTS_BASE_DIR.iterdir():
                    if user_dir.is_dir():
                        user_name = user_dir.name
                        agents_dir = user_dir / "agents"
                        if agents_dir.exists():
                            for agent_file in agents_dir.glob("*_agent.py"):
                                agent_name = agent_file.stem.replace("_agent", "")
                                agent_key = f"{user_name}/{agent_name}"
                                
                                supervisor_info = supervisor_agents.get(agent_key, {
                                    "status": "NOT_CONFIGURED",
                                    "is_active": False,
                                    "pid": None
                                })
                                
                                agents.append({
                                    "agent": f"{user_name}/{agent_name}",
                                    "file_exists": True,
                                    "is_active_in_background": supervisor_info["is_active"],
                                    "status": supervisor_info["status"],
                                    "pid": supervisor_info["pid"]
                                })
        
        # Add any supervisor-configured agents that don't have files
        for agent_key, info in supervisor_agents.items():
            if not any(agent["agent"] == agent_key for agent in agents):
                agents.append({
                    "agent": agent_key,
                    "file_exists": False,
                    "is_active_in_background": info["is_active"],
                    "status": info["status"],
                    "pid": info["pid"]
                })
            
        return agents

    async def get_agent(self, agent_name: str, username: str) -> Dict:
        """Get agent details"""
        agents_dir, _ = self._get_user_directories(username)
        agent_file = agents_dir / f"{agent_name}_agent.py"
        
        if not agent_file.exists():
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found for user '{username}'")
        
        try:
            program_name = f"{username}_{agent_name}_agent"
            result = subprocess.run(
                ["supervisorctl", "status", program_name],
                capture_output=True, text=True
            )
            status = "unknown"
            if result.returncode == 0:
                status_line = result.stdout.strip()
                if status_line:
                    status = status_line.split()[1]
        except:
            status = "unknown"
        
        return {
            "name": agent_name,
            "username": username,
            "status": status,
            "file": str(agent_file),
            "exists": True
        }

manager = AgentManager()

@app.post("/agents")
async def create_agent(config: AgentConfig):
    """Create a new agent"""
    return await manager.create_agent(config)

@app.get("/agents")
async def list_agents(username: str = None):
    """List all agents for a specific user or all users"""
    return await manager.list_agents(username)

@app.get("/agents/{agent_name}")
async def get_agent(agent_name: str, username: str):
    """Get agent details"""
    return await manager.get_agent(agent_name, username)

@app.post("/agents/{agent_name}/start")
async def start_agent(agent_name: str, username: str):
    """Start an agent"""
    return await manager.start_agent(agent_name, username)

@app.post("/agents/{agent_name}/stop")
async def stop_agent(agent_name: str, username: str):
    """Stop an agent"""
    return await manager.stop_agent(agent_name, username)

@app.delete("/agents/{agent_name}")
async def delete_agent(agent_name: str, username: str):
    """Delete an agent"""
    return await manager.delete_agent(agent_name, username)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)