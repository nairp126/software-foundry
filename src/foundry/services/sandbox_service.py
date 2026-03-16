"""Docker-based sandboxing service for safe code execution."""

import os
import subprocess
import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

class SandboxService:
    """Service for executing code in isolated Docker containers."""

    def __init__(self):
        # Maps project languages to Docker images
        self.image_map = {
            "python": "python:3.11-slim",
            "javascript": "node:18-slim",
            "typescript": "node:18-slim",
        }
        
        # Maps languages to default execution commands
        self.default_commands = {
            "python": "python main.py",
            "javascript": "node main.js",
            "typescript": "ts-node main.ts",
        }

    async def execute_project(
        self,
        project_id: str,
        project_path: str,
        language: str = "python",
        command: Optional[str] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Execute project code in a temporary Docker container.
        
        Args:
            project_id: Unique project identifier
            project_path: Absolute path to the code on the host/volume
            language: Programming language environment
            command: Override the default execution command
            timeout: Maximum execution time in seconds
            
        Returns:
            Dictionary with result (stdout, stderr, exit_code, success)
        """
        image = self.image_map.get(language.lower(), "python:3.11-slim")
        exec_cmd = command or self.default_commands.get(language.lower(), "python main.py")
        
        container_name = f"foundry-sandbox-{project_id[:8]}-{int(time.time())}"
        
        # Note: Since the Foundry itself runs inside Docker, we assume project_path 
        # is a path that is accessible to the host's Docker daemon.
        # If Foundry is in a container, project_path must be the HOST path or 
        # we must use volumes-from or similar strategies.
        # For our specific docker-compose setup, we use a bind mount to ./generated_projects.
        
        # WARNING: This assumes the Docker daemon is reachable from the current environment.
        # In our docker-compose, we mount /var/run/docker.sock.
        
        # Construct the docker command
        # We mount the project path to /app in the container
        docker_args = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", "none",  # Security: No internet access
            "--memory", "512m",   # Limit resources
            "--cpus", "0.5",
            "-v", f"{project_path}:/app",
            "-w", "/app",
            image,
            "sh", "-c", exec_cmd
        ]
        
        logger.info(f"Starting sandbox for {project_id} with command: {exec_cmd}")
        
        try:
            # Run synchronously for now (subprocess.run) since this is called from a worker
            process = subprocess.run(
                docker_args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "success": process.returncode == 0,
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
            
        except subprocess.TimeoutExpired as e:
            # Kill the container if it's still running
            subprocess.run(["docker", "stop", "-t", "0", container_name], capture_output=True)
            return {
                "success": False,
                "exit_code": -1,
                "stdout": e.stdout or "",
                "stderr": f"Execution timed out after {timeout}s",
            }
        except Exception as e:
            logger.error(f"Sandbox execution failed: {e}")
            return {
                "success": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": str(e),
            }

sandbox_service = SandboxService()
