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
        entry_point: str = "main.py"
    ) -> Dict[str, Any]:
        """Execute project code in a temporary Docker container.
        
        Args:
            project_id: Unique project identifier
            project_path: Absolute path to the code on the host/volume
            language: Programming language environment
            command: Override the default execution command
            timeout: Maximum execution time in seconds
            entry_point: The file to execute (if command is not provided)
            
        Returns:
            Dictionary with result (stdout, stderr, exit_code, success)
        """
        import asyncio
        import time

        image = self.image_map.get(language.lower(), "python:3.11-slim")
        
        # Check if entry_point exists in src/ if it's not found in root
        actual_entry_point = entry_point
        local_project_path = project_path
        
        # Determine the relative path to the entry point within the sandbox
        # If the file is in src/ but we are mounting project root to /app
        # the command should be 'python src/main.py'
        if not command:
            if language.lower() == "python":
                exec_cmd = f"python {entry_point}"
            elif language.lower() in ("javascript", "typescript"):
                exec_cmd = f"node {entry_point}" if entry_point.endswith(".js") else f"npx ts-node {entry_point}"
            else:
                exec_cmd = self.default_commands.get(language.lower(), "python main.py")
        else:
            exec_cmd = command

        # SECURITY: If the entry_point is actually in a src/ folder (common in generated code)
        # and the user just said 'main.py', we should try to find it.
        # But in a sandbox we are running 'sh -c exec_cmd'.
        # We can make it more robust by checking for the file in /app/src/main.py
        if not command:
            robust_exec_cmd = f"if [ -f {entry_point} ]; then {exec_cmd}; elif [ -f src/{entry_point} ]; then cd src && {exec_cmd}; else {exec_cmd}; fi"
            exec_cmd = robust_exec_cmd

        # Construct the docker command
        container_name = f"foundry-sandbox-{project_id}-{int(time.time())}"
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
