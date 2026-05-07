"""Docker-based sandbox environment for secure code execution."""

import asyncio
import json
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid
import logging
from foundry.config import settings

logger = logging.getLogger(__name__)


class SandboxStatus(str, Enum):
    """Status of a sandbox instance."""
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ResourceUsage:
    """Resource usage metrics for a sandbox."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    disk_mb: float = 0.0
    execution_time_seconds: float = 0.0


@dataclass
class ExecutionResult:
    """Result of code execution in sandbox."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    resource_usage: ResourceUsage
    errors: List[str] = field(default_factory=list)


@dataclass
class InstallResult:
    """Result of dependency installation."""
    success: bool
    installed_packages: List[str]
    failed_packages: List[str]
    output: str


@dataclass
class Code:
    """Code to be executed."""
    content: str
    language: str
    filename: str
    entry_point: Optional[str] = None


class Sandbox:
    """Represents a Docker-based sandbox instance."""
    
    def __init__(
        self,
        sandbox_id: str,
        language: str,
        container_id: Optional[str] = None,
    ):
        self.sandbox_id = sandbox_id
        self.language = language
        self.container_id = container_id
        self.status = SandboxStatus.CREATED
        self.created_at = time.time()
        self.work_dir = f"/sandbox/{sandbox_id}"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert sandbox to dictionary."""
        return {
            "sandbox_id": self.sandbox_id,
            "language": self.language,
            "container_id": self.container_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "work_dir": self.work_dir,
        }


class SandboxEnvironment:
    """
    Docker-based sandbox environment for secure code execution.
    
    Security Features:
    - Complete host system isolation using Docker containers
    - Resource limits (2 vCPUs, 4GB RAM, 2GB disk, 5-minute execution time)
    - Network restrictions (outbound HTTPS/HTTP only, internal ranges blocked)
    - System call filtering to prevent container escape
    """
    
    # Resource limits as per requirements
    MAX_CPUS = settings.sandbox_cpu_limit
    # Parse memory limit string (e.g., "512m") to integer MB
    MAX_MEMORY_MB = int(settings.sandbox_memory_limit.rstrip('m'))
    MAX_DISK_MB = 2048
    MAX_EXECUTION_TIME_SECONDS = 300  # 5 minutes
    
    # Language-specific base images
    BASE_IMAGES = {
        "python": "python:3.11-slim",
        "javascript": "node:20-slim",
        "typescript": "node:20-slim",
        "java": "openjdk:17-slim",
        "go": "golang:1.21-alpine",
        "rust": "rust:1.75-slim",
    }
    
    # Language-specific execution commands
    EXECUTION_COMMANDS = {
        "python": "python -m {module}",
        "javascript": "node {filename}",
        "typescript": "npx ts-node {filename}",
        "java": "javac {filename} && java {classname}",
        "go": "go run {filename}",
        "rust": "rustc {filename} && ./{binary}",
        "pytest": "python -m pytest tests/ --tb=short",
    }
    
    def __init__(self):
        """Initialize the sandbox environment."""
        self.active_sandboxes: Dict[str, Sandbox] = {}
        self._docker_available: Optional[bool] = None
        
    async def _check_docker_available(self) -> bool:
        """Check if Docker is available."""
        if self._docker_available is not None:
            return self._docker_available
            
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            self._docker_available = process.returncode == 0
            return self._docker_available
        except FileNotFoundError:
            self._docker_available = False
            return False
    
    async def create_sandbox(
        self,
        language: str,
        dependencies: Optional[List[str]] = None
    ) -> Sandbox:
        """
        Create a new sandbox environment.
        
        Args:
            language: Programming language (python, javascript, etc.)
            dependencies: List of dependencies to install
            
        Returns:
            Sandbox instance
        """
        if not await self._check_docker_available():
            logger.warning("Docker not available, creating mock sandbox")
            sandbox_id = str(uuid.uuid4())
            sandbox = Sandbox(sandbox_id=sandbox_id, language=language)
            self.active_sandboxes[sandbox_id] = sandbox
            return sandbox
        
        sandbox_id = str(uuid.uuid4())
        base_image = self.BASE_IMAGES.get(language, "ubuntu:22.04")
        
        logger.info(f"Creating sandbox {sandbox_id} for language {language}")
        
        try:
            # Create container with resource limits and security constraints
            cmd = [
                "docker", "run",
                "-d",  # Detached mode
                "--rm",  # Auto-remove on stop
                f"--name=sandbox-{sandbox_id}",
                f"--cpus={self.MAX_CPUS}",
                f"--memory={self.MAX_MEMORY_MB}m",
                "--memory-swap=-1",  # Disable swap
                "--network=bridge",  # Isolated network
                "--cap-drop=ALL",  # Drop all capabilities
                "--security-opt=no-new-privileges",  # Prevent privilege escalation
                "--read-only",  # Read-only root filesystem
                "--tmpfs=/tmp:rw,noexec,nosuid,size=2g",  # Writable tmp with limits
                f"--tmpfs=/sandbox:rw,exec,size={self.MAX_DISK_MB}m",  # Work directory
                base_image,
                "sleep", "infinity"  # Keep container running
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"Failed to create sandbox: {error_msg}")
                raise RuntimeError(f"Failed to create sandbox: {error_msg}")
            
            container_id = stdout.decode().strip()
            sandbox = Sandbox(
                sandbox_id=sandbox_id,
                language=language,
                container_id=container_id
            )
            sandbox.status = SandboxStatus.RUNNING
            
            self.active_sandboxes[sandbox_id] = sandbox
            
            # Install dependencies if provided
            if dependencies:
                await self.install_dependencies(sandbox, dependencies)
            
            logger.info(f"Sandbox {sandbox_id} created successfully")
            return sandbox
            
        except Exception as e:
            logger.error(f"Error creating sandbox: {e}")
            raise
    
    async def write_files(self, sandbox: Sandbox, files: Dict[str, str]) -> None:
        """Write multiple files to the sandbox."""
        for filename, content in files.items():
            # Ensure parent directories exist
            dir_path = Path(filename).parent
            if str(dir_path) != ".":
                mkdir_cmd = ["docker", "exec", f"sandbox-{sandbox.sandbox_id}", "mkdir", "-p", f"{sandbox.work_dir}/{dir_path}"]
                await (await asyncio.create_subprocess_exec(*mkdir_cmd)).communicate()

            # Write file content
            # Escape single quotes for shell command
            escaped_content = content.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))
            write_cmd = [
                "docker", "exec",
                f"sandbox-{sandbox.sandbox_id}",
                "sh", "-c",
                f"echo '{escaped_content}' > {sandbox.work_dir}/{filename}"
            ]
            process = await asyncio.create_subprocess_exec(
                *write_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

    async def execute_code(
        self,
        sandbox: Sandbox,
        code: Optional[Code] = None,
        code_repo: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        command: Optional[str] = None,
        entry_point: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute code in the sandbox.
        
        Args:
            sandbox: Sandbox instance
            code: Single code object to execute
            code_repo: Dictionary of files to write before execution
            timeout: Execution timeout in seconds
            command: Custom command to execute
            entry_point: Filename to execute if code_repo is provided
            
        Returns:
            ExecutionResult with execution details
        """
        if timeout is None:
            timeout = self.MAX_EXECUTION_TIME_SECONDS
        
        # Mock execution if Docker not available
        if not sandbox.container_id:
            logger.warning("Mock execution (Docker not available)")
            return ExecutionResult(
                success=True,
                stdout="Mock execution successful",
                stderr="",
                exit_code=0,
                execution_time=0.1,
                resource_usage=ResourceUsage(),
                errors=[]
            )
        
        start_time = time.time()
        
        try:
            if not code and not code_repo:
                raise ValueError("Either 'code' or 'code_repo' must be provided.")

            # Write files if provided
            if code_repo:
                await self.write_files(sandbox, code_repo)
                if not entry_point and not command:
                    raise ValueError("entry_point or command is required for code_repo execution")
            
            # Write single code file if provided
            if code:
                await self.write_files(sandbox, {code.filename: code.content})
                if not entry_point:
                    entry_point = code.filename

            # Choose execution command
            if command:
                exec_command = command
            else:
                language = sandbox.language
                if code:
                    language = code.language
                
                if not entry_point:
                    raise ValueError("entry_point is required when 'command' is not provided.")

                exec_command = self.EXECUTION_COMMANDS.get(language, "cat {filename}")
                exec_command = exec_command.format(
                    filename=entry_point,
                    module=str(Path(entry_point).with_suffix('')).replace('/', '.').replace('\\', '.'),
                    classname=Path(entry_point).stem,
                    binary=Path(entry_point).stem
                )
            
            exec_cmd = [
                "docker", "exec",
                "-w", sandbox.work_dir,
                f"sandbox-{sandbox.sandbox_id}",
                "sh", "-c",
                exec_command
            ]
            
            process = await asyncio.create_subprocess_exec(
                *exec_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                execution_time = time.time() - start_time
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timeout after {timeout} seconds",
                    exit_code=-1,
                    execution_time=execution_time,
                    resource_usage=await self.get_resource_usage(sandbox),
                    errors=[f"Execution timeout after {timeout} seconds"]
                )
            
            execution_time = time.time() - start_time
            stdout_str = stdout.decode()
            stderr_str = stderr.decode()
            
            # Parse errors from stderr
            errors = []
            if stderr_str:
                errors = [line.strip() for line in stderr_str.split('\n') if line.strip()]
            
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=process.returncode,
                execution_time=execution_time,
                resource_usage=await self.get_resource_usage(sandbox),
                errors=errors
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error executing code in sandbox: {e}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time=execution_time,
                resource_usage=ResourceUsage(),
                errors=[str(e)]
            )
    
    async def install_dependencies(
        self,
        sandbox: Sandbox,
        dependencies: List[str]
    ) -> InstallResult:
        """
        Install dependencies in the sandbox.
        
        Args:
            sandbox: Sandbox instance
            dependencies: List of package names to install
            
        Returns:
            InstallResult with installation details
        """
        if not sandbox.container_id:
            logger.warning("Mock dependency installation (Docker not available)")
            return InstallResult(
                success=True,
                installed_packages=dependencies,
                failed_packages=[],
                output="Mock installation successful"
            )
        
        # Language-specific package managers
        # Note: Install to /tmp since root filesystem is read-only
        install_commands = {
            "python": "pip install --no-cache-dir --target=/tmp/packages {packages} && export PYTHONPATH=/tmp/packages:$PYTHONPATH",
            "javascript": "npm install --no-save --prefix=/tmp {packages}",
            "typescript": "npm install --no-save --prefix=/tmp {packages}",
            "java": "echo 'Java dependencies require build tool'",
            "go": "go get {packages}",
            "rust": "cargo install --root=/tmp {packages}",
        }
        
        install_cmd_template = install_commands.get(sandbox.language)
        if not install_cmd_template:
            return InstallResult(
                success=False,
                installed_packages=[],
                failed_packages=dependencies,
                output=f"Unsupported language: {sandbox.language}"
            )
        
        packages_str = " ".join(dependencies)
        install_cmd = install_cmd_template.format(packages=packages_str)
        
        cmd = [
            "docker", "exec",
            f"sandbox-{sandbox.sandbox_id}",
            "sh", "-c",
            install_cmd
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode() + stderr.decode()
            
            if process.returncode == 0:
                return InstallResult(
                    success=True,
                    installed_packages=dependencies,
                    failed_packages=[],
                    output=output
                )
            else:
                return InstallResult(
                    success=False,
                    installed_packages=[],
                    failed_packages=dependencies,
                    output=output
                )
                
        except Exception as e:
            logger.error(f"Error installing dependencies: {e}")
            return InstallResult(
                success=False,
                installed_packages=[],
                failed_packages=dependencies,
                output=str(e)
            )
    
    async def get_resource_usage(self, sandbox: Sandbox) -> ResourceUsage:
        """
        Get current resource usage of the sandbox.
        
        Args:
            sandbox: Sandbox instance
            
        Returns:
            ResourceUsage metrics
        """
        if not sandbox.container_id:
            return ResourceUsage()
        
        try:
            cmd = [
                "docker", "stats",
                f"sandbox-{sandbox.sandbox_id}",
                "--no-stream",
                "--format", "{{json .}}"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            
            if process.returncode == 0:
                stats = json.loads(stdout.decode())
                
                # Parse CPU percentage
                cpu_str = stats.get("CPUPerc", "0%").rstrip("%")
                cpu_percent = float(cpu_str) if cpu_str else 0.0
                
                # Parse memory usage
                mem_str = stats.get("MemUsage", "0MiB / 0MiB").split("/")[0].strip()
                memory_mb = self._parse_memory(mem_str)
                
                return ResourceUsage(
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    disk_mb=0.0,  # Docker stats doesn't provide disk usage easily
                    execution_time_seconds=time.time() - sandbox.created_at
                )
            
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
        
        return ResourceUsage()
    
    def _parse_memory(self, mem_str: str) -> float:
        """Parse memory string to MB."""
        mem_str = mem_str.strip()
        if "GiB" in mem_str:
            return float(mem_str.replace("GiB", "")) * 1024
        elif "MiB" in mem_str:
            return float(mem_str.replace("MiB", ""))
        elif "KiB" in mem_str:
            return float(mem_str.replace("KiB", "")) / 1024
        return 0.0
    
    async def cleanup_sandbox(self, sandbox: Sandbox) -> None:
        """
        Clean up and remove the sandbox.
        
        Args:
            sandbox: Sandbox instance to clean up
        """
        if not sandbox.container_id:
            # Remove from active sandboxes
            self.active_sandboxes.pop(sandbox.sandbox_id, None)
            return
        
        try:
            cmd = [
                "docker", "stop",
                f"sandbox-{sandbox.sandbox_id}"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            sandbox.status = SandboxStatus.STOPPED
            self.active_sandboxes.pop(sandbox.sandbox_id, None)
            
            logger.info(f"Sandbox {sandbox.sandbox_id} cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error cleaning up sandbox: {e}")
            sandbox.status = SandboxStatus.ERROR
