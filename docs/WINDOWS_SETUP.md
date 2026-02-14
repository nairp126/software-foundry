# Windows Setup Guide for LLM Inference

This guide provides Windows-specific instructions for running Qwen models locally.

## Problem: vLLM Windows Support

vLLM currently has limited native Windows support due to PyTorch dependency conflicts. The error you're seeing:
```
ERROR: Could not find a version that satisfies the requirement torch==2.6.0
```

This occurs because vLLM requires specific PyTorch versions that aren't available for Windows.

## Solutions for Windows Users

### Option 1: WSL2 (Recommended) ⭐

Windows Subsystem for Linux 2 provides the best compatibility and performance.

#### Step 1: Install WSL2

```powershell
# Run in PowerShell as Administrator
wsl --install
```

Or install Ubuntu specifically:
```powershell
wsl --install -d Ubuntu-22.04
```

Restart your computer after installation.

#### Step 2: Install NVIDIA CUDA on WSL2

```bash
# Inside WSL2 Ubuntu terminal
# Update package list
sudo apt update && sudo apt upgrade -y

# Install NVIDIA CUDA Toolkit
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda-toolkit-12-6

# Verify CUDA installation
nvidia-smi
```

#### Step 3: Install Python and vLLM in WSL2

```bash
# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# Create virtual environment
python3.11 -m venv ~/vllm-env
source ~/vllm-env/bin/activate

# Install vLLM
pip install vllm
```

#### Step 4: Start vLLM Server

```bash
# Activate environment
source ~/vllm-env/bin/activate

# Start vLLM server
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype auto \
  --max-model-len 8192
```

#### Step 5: Access from Windows

The vLLM server running in WSL2 is accessible from Windows at:
```
http://localhost:8001
```

Update your `.env` file:
```bash
VLLM_BASE_URL=http://localhost:8001/v1
```

### Option 2: Docker Desktop with WSL2 Backend

#### Step 1: Install Docker Desktop

1. Download Docker Desktop for Windows: https://www.docker.com/products/docker-desktop/
2. Install with WSL2 backend enabled
3. Restart your computer

#### Step 2: Enable GPU Support

In Docker Desktop settings:
- Go to Settings → Resources → WSL Integration
- Enable integration with your WSL2 distro
- Apply & Restart

#### Step 3: Run vLLM in Docker

Create `docker-compose.vllm.yml`:

```yaml
version: '3.8'

services:
  vllm:
    image: vllm/vllm-openai:latest
    container_name: vllm-server
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    ports:
      - "8001:8000"
    command: >
      --model Qwen/Qwen2.5-Coder-32B-Instruct
      --host 0.0.0.0
      --port 8000
      --dtype auto
      --max-model-len 8192
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Start the container:
```powershell
docker-compose -f docker-compose.vllm.yml up -d
```

### Option 3: Ollama (Windows Native) ⚡

Ollama provides native Windows support and is easier to set up, though with slightly different performance characteristics.

#### Step 1: Install Ollama

1. Download Ollama for Windows: https://ollama.com/download/windows
2. Run the installer
3. Ollama will start automatically

#### Step 2: Pull Qwen Model

```powershell
# Pull Qwen2.5-Coder model
ollama pull qwen2.5-coder:32b

# Or smaller version
ollama pull qwen2.5-coder:14b
```

#### Step 3: Run Ollama Server

Ollama runs automatically as a Windows service on `http://localhost:11434`

#### Step 4: Update Foundry Configuration

Create an Ollama provider (we'll need to implement this):

```python
# src/foundry/llm/ollama_provider.py
# TODO: Implement Ollama provider similar to vLLM provider
```

For now, you can use Ollama's OpenAI-compatible API:

Update `.env`:
```bash
VLLM_BASE_URL=http://localhost:11434/v1
VLLM_MODEL_NAME=qwen2.5-coder:32b
```

**Note**: Ollama's API is slightly different from vLLM. We'll need to create a dedicated Ollama provider for full compatibility.

### Option 4: Cloud-Based vLLM (Temporary Solution)

While setting up local inference, you can use cloud-based alternatives:

#### RunPod

1. Sign up at https://www.runpod.io/
2. Deploy a vLLM template with Qwen model
3. Get the endpoint URL
4. Update `.env`:
```bash
VLLM_BASE_URL=https://your-runpod-endpoint.com/v1
VLLM_API_KEY=your-api-key
```

#### Together.ai

1. Sign up at https://together.ai/
2. Get API key
3. Update `.env`:
```bash
VLLM_BASE_URL=https://api.together.xyz/v1
VLLM_API_KEY=your-together-api-key
VLLM_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct
```

## Recommended Approach for Windows

**For Development:**
1. Use **WSL2** (Option 1) - Best compatibility and performance
2. Install Ubuntu 22.04 in WSL2
3. Install CUDA in WSL2
4. Run vLLM in WSL2
5. Access from Windows at `localhost:8001`

**For Quick Testing:**
1. Use **Ollama** (Option 3) - Easiest setup
2. Native Windows support
3. Good performance
4. Slightly different API (requires adapter)

**For Production:**
1. Use **Docker** (Option 2) - Consistent environment
2. Easy deployment
3. GPU passthrough via WSL2

## Troubleshooting

### WSL2 GPU Not Detected

```bash
# Check if GPU is visible in WSL2
nvidia-smi

# If not visible, update WSL2
wsl --update
wsl --shutdown
# Restart WSL2
```

### Docker GPU Not Working

1. Ensure Docker Desktop is using WSL2 backend
2. Enable GPU support in Docker Desktop settings
3. Install NVIDIA Container Toolkit in WSL2:

```bash
# In WSL2
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### Ollama Model Not Loading

```powershell
# Check Ollama status
ollama list

# Restart Ollama service
# Open Services (services.msc)
# Find "Ollama" service
# Restart it
```

### Port Already in Use

```powershell
# Find process using port 8001
netstat -ano | findstr :8001

# Kill process (replace PID)
taskkill /PID <PID> /F
```

## Performance Comparison

| Solution | Setup Time | Performance | Compatibility | Recommended For |
|----------|-----------|-------------|---------------|-----------------|
| WSL2 + vLLM | 30-60 min | Excellent | High | Development & Production |
| Docker + vLLM | 15-30 min | Excellent | High | Production |
| Ollama | 5-10 min | Good | Medium | Quick Testing |
| Cloud vLLM | 5 min | Good | High | Temporary/Testing |

## Next Steps

After setting up your chosen solution:

1. **Verify Installation**:
```bash
curl http://localhost:8001/v1/models
```

2. **Update Configuration**:
Edit `.env` with correct `VLLM_BASE_URL`

3. **Test Integration**:
```bash
python -m foundry.llm.test
```

4. **Proceed with Development**:
Continue with Task 2 (Agent Orchestration)

## Additional Resources

- WSL2 Installation: https://learn.microsoft.com/en-us/windows/wsl/install
- NVIDIA CUDA on WSL2: https://docs.nvidia.com/cuda/wsl-user-guide/
- Docker Desktop: https://docs.docker.com/desktop/windows/wsl/
- Ollama: https://ollama.com/
- vLLM Documentation: https://docs.vllm.ai/

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review vLLM GitHub issues: https://github.com/vllm-project/vllm/issues
3. Check WSL2 documentation for GPU support
4. Consider using Ollama as a simpler alternative
