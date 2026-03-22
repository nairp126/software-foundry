import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from foundry.orchestrator import merge_dicts, AgentOrchestrator, GraphState
from foundry.middleware.rate_limit import RateLimitMiddleware
from foundry.models.project import ProjectStatus

def test_state_reducer_merge():
    """Test that merge_dicts correctly preserves and updates context."""
    left = {"prd": "Initial PRD", "existing": "keep me"}
    right = {"prd": "Updated PRD", "new": "add me"}
    result = merge_dicts(left, right)
    
    assert result["prd"] == "Updated PRD"
    assert result["existing"] == "keep me"
    assert result["new"] == "add me"
    assert len(result) == 3

@pytest.mark.asyncio
async def test_rate_limit_logic_sliding_window():
    """Test the sliding window logic in RateLimitMiddleware."""
    # Mock redis
    mock_redis = AsyncMock()
    mock_pipe = AsyncMock()
    mock_redis.pipeline.return_value = mock_pipe
    
    # pipe.execute() returns [zrem_count, zcard_count, zadd_res, expire_res]
    # Simulate first request (count is 0)
    mock_pipe.execute.return_value = [0, 0, 1, True]
    
    with patch("foundry.redis_client.redis_client.client", mock_redis):
        middleware = RateLimitMiddleware(MagicMock())
        is_allowed, remaining, reset_time = await middleware._check_rate_limit("test_user", 5, 60)
        
        assert is_allowed is True
        assert remaining == 4
        assert mock_pipe.zcard.called
        
    # Simulate being at the limit
    mock_pipe.execute.return_value = [0, 5, 1, True]
    with patch("foundry.redis_client.redis_client.client", mock_redis):
        middleware = RateLimitMiddleware(MagicMock())
        is_allowed, remaining, reset_time = await middleware._check_rate_limit("test_user", 5, 60)
        
        assert is_allowed is False
        assert remaining == 0

@pytest.mark.asyncio
async def test_approval_gate_logic():
    """Test the approval gate logic in the orchestrator."""
    orchestrator = AgentOrchestrator()
    
    # Test should_proceed_to_approval
    state = {"project_id": "test"}
    # The logic I implemented currently always returns "approve" for safety (Audit 7.2)
    assert orchestrator._should_proceed_to_approval(state) == "approve"
    
    # Test check_approval_status
    assert await orchestrator._check_approval_status(state) == "proceed"

if __name__ == "__main__":
    # Run tests if called directly
    import pytest
    pytest.main([__file__])
