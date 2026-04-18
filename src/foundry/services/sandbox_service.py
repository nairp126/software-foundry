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
            "javascript": "node:20-slim",
            "typescript": "node:20-slim",
            "java": "openjdk:17-slim",
            "go": "golang:1.21-alpine",
            "rust": "rust:1.75-slim",
        }
        
        # Maps languages to default execution commands
        self.default_commands = {
            "python": "python main.py",
            "javascript": "node main.js",
            "typescript": "npx ts-node main.ts",
            "java": "javac Main.java && java Main",
            "go": "go run main.go",
            "rust": "rustc main.rs && ./main",
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
        import asyncio
        import time

        image = self.image_map.get(language.lower(), "python:3.11-slim")
        exec_cmd = command or self.default_commands.get(language.lower(), "python main.py")
        
        # Check for host path configuration in Dockerized environments
        from foundry.config import settings
        if os.path.exists("/.dockerenv") and not settings.host_generated_projects_path:
            logger.warning(
                "RUNNING IN DOCKER: 'HOST_GENERATED_PROJECTS_PATH' is not set. "
                "Docker volume mounting may fail if the host path is different from the container path."
            )
        
        container_name = f"foundry-sandbox-{project_id[:8]}-{int(time.time())}"
        
        # Construct the docker command
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
        
        logger.info(f"Starting async sandbox for {project_id} with command: {exec_cmd}")
        
        try:
            # SANDBOX-BUG-1: Use async subprocess to avoid blocking the event loop
            process = await asyncio.create_subprocess_exec(
                *docker_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                return {
                    "success": process.returncode == 0,
                    "exit_code": process.returncode,
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                }
            except asyncio.TimeoutError:
                # Kill the container if it's still running
                stop_process = await asyncio.create_subprocess_exec(
                    "docker", "stop", "-t", "0", container_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await stop_process.communicate()
                return {
                    "success": False,
                    "exit_code": -1,
                    "stdout": "",
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
