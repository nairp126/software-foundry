"""Smoke test for Patent 3: Semantic Completeness Verification."""
import asyncio
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Patent3SmokeTest")

from foundry.agents.reflexion import ReflexionEngine
from foundry.sandbox.environment import ExecutionResult, ResourceUsage
from foundry.metrics.surgical_context_metrics import SurgicalContextMetrics

async def test_patent3():
    engine = ReflexionEngine()

    # ===== Test 1: Python stub detection (all 4 patterns) =====
    logger.info("Test 1: Python multi-pattern stub detection")
    python_repo = {
        "service.py": '''
def get_user(user_id):
    """Fetch a user."""
    pass

def delete_user(user_id):
    ...

def update_user(user_id, data):
    raise NotImplementedError

def create_user(data):
    """Creates a new user."""
    return None
''',
        "utils.py": '''
def real_function():
    return {"status": "ok"}
''',
        "__init__.py": "# init",
    }
    
    stubs = engine._find_stub_files(python_repo, "python")
    assert "service.py" in stubs, f"Expected service.py in stubs, got: {stubs}"
    assert "utils.py" not in stubs, f"utils.py should NOT be in stubs"
    assert "__init__.py" not in stubs, "__init__.py should be skipped"
    
    # Verify all 4 function names were detected
    desc = stubs["service.py"]
    for name in ["get_user", "delete_user", "update_user", "create_user"]:
        assert name in desc, f"Expected '{name}' in stub description, got: {desc}"
    logger.info(f"  PASS: Detected stubs: {stubs}")

    # ===== Test 2: JavaScript stub detection =====
    logger.info("Test 2: JavaScript stub detection")
    js_repo = {
        "handler.js": '''
function getUser(id) {}

const deleteUser = (id) => {}

function createUser(data) {
    throw new Error("not implemented")
}

function updateUser(data) {
    console.log('TODO')
}
''',
        "real.js": '''
function realHandler(req, res) {
    res.send("hello");
}
''',
    }
    
    stubs_js = engine._find_stub_files(js_repo, "javascript")
    assert "handler.js" in stubs_js, f"Expected handler.js in stubs, got: {stubs_js}"
    assert "real.js" not in stubs_js, f"real.js should NOT be in stubs"
    desc_js = stubs_js["handler.js"]
    for name in ["getUser", "deleteUser", "createUser", "updateUser"]:
        assert name in desc_js, f"Expected '{name}' in JS stub description, got: {desc_js}"
    logger.info(f"  PASS: JS stubs detected: {stubs_js}")

    # ===== Test 3: TypeScript is also matched =====
    logger.info("Test 3: TypeScript detection")
    ts_repo = {
        "api.ts": 'function fetchData(url) {}',
    }
    stubs_ts = engine._find_stub_files(ts_repo, "typescript")
    assert "api.ts" in stubs_ts, f"Expected api.ts in stubs, got: {stubs_ts}"
    logger.info(f"  PASS: TS stubs detected: {stubs_ts}")

    # ===== Test 4: _synthesize_semantic_failure =====
    logger.info("Test 4: Semantic failure synthesis")
    mock_result = ExecutionResult(
        success=True,
        stdout="All tests passed",
        stderr="",
        exit_code=0,
        execution_time=1.5,
        resource_usage=ResourceUsage(cpu_percent=10.0, memory_mb=100.0, disk_mb=0.5),
        errors=[]
    )
    
    synth = engine._synthesize_semantic_failure(stubs, mock_result)
    assert synth.success is False, "Synthesized result should be a failure"
    assert synth.exit_code == 1, "Exit code should be 1"
    assert "SEMANTIC_COMPLETENESS_FAILURE" in synth.stderr, f"stderr should contain failure tag, got: {synth.stderr}"
    assert synth.stdout == "All tests passed", "stdout should be preserved from prior result"
    assert len(synth.errors) == len(stubs), "errors list should have one entry per stub file"
    logger.info(f"  PASS: Synthesized failure: success={synth.success}, errors={synth.errors}")

    # ===== Test 5: SurgicalContextMetrics has stub fields =====
    logger.info("Test 5: SurgicalContextMetrics stub fields")
    m = SurgicalContextMetrics(
        file_path="test.py",
        stub_functions_detected=3,
        stub_detection_triggered=True,
        model_name="qwen2.5-coder:1.5b"
    )
    assert m.stub_functions_detected == 3
    assert m.stub_detection_triggered is True
    assert m.model_name == "qwen2.5-coder:1.5b"
    logger.info(f"  PASS: Metrics fields verified")

    # ===== Test 6: Java stub detection =====
    logger.info("Test 6: Java stub detection")
    java_repo = {
        "Service.java": '''
class Service {
    public void getUser(String id) {}
    public void deleteUser(String id) {
        throw new UnsupportedOperationException();
    }
    public void updateUser(String id) {
        // TODO: implement this
    }
}
'''
    }
    stubs_java = engine._find_stub_files(java_repo, "java")
    assert "Service.java" in stubs_java, f"Expected Service.java in stubs, got: {stubs_java}"
    desc_java = stubs_java["Service.java"]
    # For Java, getUser is captured, but deleteUser/updateUser might be 'unknown'
    assert "getUser" in desc_java
    assert "unknown" in desc_java
    logger.info(f"  PASS: Java stubs detected: {stubs_java}")

    # ===== Test 7: Go stub detection =====
    logger.info("Test 7: Go stub detection")
    go_repo = {
        "api.go": '''
func GetUser(id string) {}
func DeleteUser(id string) {
    panic("not implemented")
}
func UpdateUser(id string) {
    // TODO
}
'''
    }
    stubs_go = engine._find_stub_files(go_repo, "go")
    assert "api.go" in stubs_go, f"Expected api.go in stubs, got: {stubs_go}"
    desc_go = stubs_go["api.go"]
    assert "GetUser" in desc_go
    assert "unknown" in desc_go
    logger.info(f"  PASS: Go stubs detected: {stubs_go}")

    # ===== Test 8: Rust stub detection =====
    logger.info("Test 8: Rust stub detection")
    rust_repo = {
        "main.rs": '''
fn get_user(id: String) {}
fn delete_user(id: String) {
    todo!()
}
fn update_user(id: String) {
    unimplemented!()
}
'''
    }
    stubs_rust = engine._find_stub_files(rust_repo, "rust")
    assert "main.rs" in stubs_rust, f"Expected main.rs in stubs, got: {stubs_rust}"
    desc_rust = stubs_rust["main.rs"]
    assert "get_user" in desc_rust
    assert "unknown" in desc_rust
    logger.info(f"  PASS: Rust stubs detected: {stubs_rust}")

    logger.info("ALL PATENT 3 MULTI-LANGUAGE TESTS PASSED ✓")

if __name__ == "__main__":
    asyncio.run(test_patent3())
