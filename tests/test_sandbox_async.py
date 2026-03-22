import asyncio
import unittest
from unittest.mock import AsyncMock, patch
import os
import sys

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from foundry.services.sandbox_service import SandboxService

class TestSandboxServiceAsync(unittest.IsolatedAsyncioTestCase):
    
    async def test_execute_project_is_async(self):
        service = SandboxService()
        
        # Patch asyncio.create_subprocess_exec
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"output", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process
            
            result = await service.execute_project(
                project_id="test",
                project_path="/tmp/test",
                language="python"
            )
            
            self.assertTrue(mock_exec.called)
            self.assertTrue(result["success"])
            self.assertEqual(result["stdout"], "output")
            print("Verified: execute_project uses asyncio.create_subprocess_exec")

    async def test_language_support(self):
        service = SandboxService()
        self.assertIn("java", service.image_map)
        self.assertIn("go", service.image_map)
        self.assertIn("rust", service.image_map)
        
        self.assertEqual(service.image_map["java"], "openjdk:17-slim")
        print("Verified: Expanded language support (Java, Go, Rust) in SandboxService")

    async def test_timeout_logic(self):
        service = SandboxService()
        
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # First for run, second for stop
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = asyncio.TimeoutError
            mock_exec.return_value = mock_process
            
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                with patch("asyncio.create_subprocess_exec") as mock_stop_exec:
                    mock_stop_process = AsyncMock()
                    mock_stop_process.communicate.return_value = (b"", b"")
                    mock_stop_exec.return_value = mock_stop_process
                    
                    result = await service.execute_project(
                        project_id="test",
                        project_path="/tmp/test",
                        language="python",
                        timeout=1
                    )
                    
                    self.assertFalse(result["success"])
                    self.assertIn("timed out", result["stderr"])
                    self.assertTrue(mock_stop_exec.called)
                    print("Verified: Timeout logic correctly stops Docker container asynchronously")

if __name__ == "__main__":
    unittest.main()
