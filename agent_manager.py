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
AGENTS_DIR = Path("/app/agents")
SUPERVISOR_AGENTS_DIR = Path("/etc/supervisor/conf.d/agents")
MAIN_DIRECTORY = Path("/app")

class SubAgent(BaseModel):
    name: str
    instruction: str
    servers: List[str] = []
    model: str = "haiku"

class AgentConfig(BaseModel):
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
        AGENTS_DIR.mkdir(exist_ok=True)
        SUPERVISOR_AGENTS_DIR.mkdir(exist_ok=True)
        
    async def create_agent(self, config: AgentConfig) -> Dict:
        """Create a new agent with the given configuration"""
        agent_file = AGENTS_DIR / f"{config.name}_agent.py"
        
        if agent_file.exists():
            raise HTTPException(status_code=400, detail=f"Agent '{config.name}' already exists")
        
        agent_code = self._generate_agent_code(config)
        agent_file.write_text(agent_code)
        
        supervisor_config = self._generate_supervisor_config(config.name)
        supervisor_file = SUPERVISOR_AGENTS_DIR / f"{config.name}.conf"
        supervisor_file.write_text(supervisor_config)
        
        return {"message": f"Agent '{config.name}' created successfully", "file": str(agent_file)}
    
    def _generate_agent_code(self, config: AgentConfig) -> str:
        """Generate Python agent code from template file"""
        template_path = Path(__file__).parent / "agent_template.py"
        
        if not template_path.exists():
            raise HTTPException(status_code=500, detail="Agent template file not found")
        
        # Read the template file
        template_content = template_path.read_text()
        
        # Replace placeholders with actual values
        agent_code = template_content.replace(
            "# PLACEHOLDER_SUBAGENTS_CONFIG - This will be replaced with actual subagents configuration\nsubagents_config = []",
            f"subagents_config = {json.dumps([agent.dict() for agent in config.subagents], indent=4)}"
        ).replace(
            "# PLACEHOLDER_JSON_CONFIG - This will be replaced with actual JSON configuration\nsample_json_config = {}",
            f"sample_json_config = {json.dumps(config.json_config, indent=4)}"
        ).replace(
            "PLACEHOLDER_AGENT_NAME",
            config.name
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
    
    def _generate_supervisor_config(self, agent_name: str) -> str:
        """Generate supervisord configuration for agent"""
        return f"""[program:{agent_name}_agent]
command=bash -c "source {MAIN_DIRECTORY}/.venv/bin/activate && python {MAIN_DIRECTORY}/agents/{agent_name}_agent.py"
directory={MAIN_DIRECTORY}/agents
autostart=false
autorestart=true
stderr_logfile={MAIN_DIRECTORY}/agents/all.log
stdout_logfile={MAIN_DIRECTORY}/agents/all.log
user=vaibhavgeek
"""

    async def start_agent(self, agent_name: str) -> Dict:
        """Start an agent using supervisorctl"""
        try:
            # Check if agent file exists first
            agent_file = AGENTS_DIR / f"{agent_name}_agent.py"
            print(agent_file)
            if not agent_file.exists():
                raise HTTPException(status_code=404, detail=f"Agent file '{agent_name}_agent.py' not found")
            
            # Check if supervisor config exists
            supervisor_file = SUPERVISOR_AGENTS_DIR / f"{agent_name}.conf"
            if not supervisor_file.exists():
                raise HTTPException(status_code=404, detail=f"Supervisor config '{agent_name}.conf' not found")
            
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
            status_check = subprocess.run(
                ["supervisorctl", "status", f"{agent_name}_agent"],
                capture_output=True, text=True
            )
            
            if status_check.returncode != 0:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Agent '{agent_name}_agent' not found in supervisor after update. "
                        f"Status check output: {status_check.stderr or status_check.stdout}"
                )
            
            # Now try to start the agent
            print(f"Starting agent '{agent_name}_agent'...")
            start_result = subprocess.run(
                ["supervisorctl", "-c" , "/opt/homebrew/etc/supervisord.conf", "start", f"{agent_name}_agent"],
                capture_output=True, text=True, check=True
            )
            
            print(f"Start output: {start_result.stdout}")
            
            # Verify the agent actually started
            final_status = subprocess.run(
                ["supervisorctl", "status", f"{agent_name}_agent"],
                capture_output=True, text=True
            )
            
            return {
                "message": f"Agent '{agent_name}' started successfully",
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
            
            error_msg = f"Failed to start agent '{agent_name}': Command '{error_details['command']}' "
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
                detail=f"Unexpected error starting agent '{agent_name}': {str(e)}"
            )

    async def stop_agent(self, agent_name: str) -> Dict:
        """Stop an agent using supervisorctl"""
        try:
            result = subprocess.run(
                ["supervisorctl", "stop", f"{agent_name}_agent"],
                capture_output=True, text=True, check=True
            )
            return {"message": f"Agent '{agent_name}' stopped successfully"}
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"Failed to stop agent: {e.stderr}")

    async def delete_agent(self, agent_name: str) -> Dict:
        """Delete an agent and its configuration"""
        agent_file = AGENTS_DIR / f"{agent_name}_agent.py"
        supervisor_file = SUPERVISOR_AGENTS_DIR / f"{agent_name}.conf"
        
        await self.stop_agent(agent_name)
        
        if agent_file.exists():
            agent_file.unlink()
        if supervisor_file.exists():
            supervisor_file.unlink()
            
        subprocess.run(["supervisorctl", "reread"], check=True)
        subprocess.run(["supervisorctl", "update"], check=True)
        
        return {"message": f"Agent '{agent_name}' deleted successfully"}

    async def list_agents(self) -> List[AgentStatus]:
        """List all agents and their status"""
        agents = []
        
        try:
            result = subprocess.run(
                ["supervisorctl", "status"],
                capture_output=True, text=True, check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if '_agent' in line and line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0].replace('_agent', '')
                        status = parts[1]
                        pid = None
                        if len(parts) > 2 and parts[2].startswith('pid'):
                            pid = int(parts[2].split()[1].rstrip(','))
                        
                        agents.append(AgentStatus(name=name, status=status, pid=pid))
                        
        except subprocess.CalledProcessError:
            pass
            
        return agents

    async def get_agent(self, agent_name: str) -> Dict:
        """Get agent details"""
        agent_file = AGENTS_DIR / f"{agent_name}_agent.py"
        
        if not agent_file.exists():
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
        
        try:
            result = subprocess.run(
                ["supervisorctl", "status", f"{agent_name}_agent"],
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
async def list_agents():
    """List all agents"""
    return await manager.list_agents()

@app.get("/agents/{agent_name}")
async def get_agent(agent_name: str):
    """Get agent details"""
    return await manager.get_agent(agent_name)

@app.post("/agents/{agent_name}/start")
async def start_agent(agent_name: str):
    """Start an agent"""
    return await manager.start_agent(agent_name)

@app.post("/agents/{agent_name}/stop")
async def stop_agent(agent_name: str):
    """Stop an agent"""
    return await manager.stop_agent(agent_name)

@app.delete("/agents/{agent_name}")
async def delete_agent(agent_name: str):
    """Delete an agent"""
    return await manager.delete_agent(agent_name)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)