# vLLM Setup Guide for Qwen Models

This guide explains how to set up vLLM to serve Qwen coding models locally for the Autonomous Software Foundry.

## Why Qwen + vLLM?

- **Cost-Effective**: No API costs, runs on your hardware
- **Privacy**: All data stays local, no external API calls
- **Performance**: vLLM provides optimized inference with continuous batching
- **Quality**: Qwen2.5-Coder models are state-of-the-art for code generation
- **Flexibility**: Full control over model selection and parameters

## Prerequisites

- NVIDIA GPU with at least 24GB VRAM (for 32B model) or 12GB VRAM (for 14B model)
- CUDA 11.8 or later
- Python 3.10 or 3.11
- 50GB+ free disk space for model weights

## Recommended Models

### Qwen2.5-Coder-32B-Instruct (Recommended)
- **VRAM**: ~24GB
- **Best for**: All agents (Product Manager, Architect, Engineering, DevOps)
- **Performance**: Excellent code generation and reasoning

### Qwen2.5-Coder-14B-Instruct (Budget Option)
- **VRAM**: ~12GB
- **Best for**: Engineering Agent, Reflexion Engine
- **Performance**: Good code generation, faster inference

### Qwen2.5-Coder-7B-Instruct (Lightweight)
- **VRAM**: ~6GB
- **Best for**: Quick iterations, testing
- **Performance**: Decent for simple tasks

## Installation

### 1. Install vLLM

```bash
# Create virtual environment
python -m venv vllm-env
source vllm-env/bin/activate  # On Windows: vllm-env\Scripts\activate

# Install vLLM with CUDA support
pip install vllm
```

### 2. Download Model (Optional)

vLLM will automatically download models on first use, but you can pre-download:

```bash
# Using Hugging Face CLI
pip install huggingface-hub
huggingface-cli download Qwen/Qwen2.5-Coder-32B-Instruct
```

### 3. Start vLLM Server

#### Option A: Basic Setup (32B Model)

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype auto \
  --max-model-len 8192
```

#### Option B: Optimized Setup (with tensor parallelism)

For multi-GPU setups:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype auto \
  --max-model-len 8192 \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.9
```

#### Option C: Budget Setup (14B Model)

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-14B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype auto \
  --max-model-len 8192
```

### 4. Verify Server is Running

```bash
curl http://localhost:8001/v1/models
```

Expected output:
```json
{
  "object": "list",
  "data": [
    {
      "id": "Qwen/Qwen2.5-Coder-32B-Instruct",
      "object": "model",
      "created": 1234567890,
      "owned_by": "vllm"
    }
  ]
}
```

## Configuration

### Update Foundry Configuration

Edit your `.env` file:

```bash
# vLLM Configuration
VLLM_BASE_URL=http://localhost:8001/v1
VLLM_API_KEY=EMPTY
VLLM_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct
DEFAULT_LLM_PROVIDER=vllm
```

### Test Integration

```python
from foundry.llm.factory import LLMProviderFactory
from foundry.llm.base import LLMMessage

# Create provider
provider = LLMProviderFactory.get_default_provider()

# Test generation
messages = [
    LLMMessage(role="system", content="You are a helpful coding assistant."),
    LLMMessage(role="user", content="Write a Python function to calculate fibonacci numbers.")
]

response = await provider.generate(messages)
print(response.content)
```

## Performance Tuning

### GPU Memory Optimization

```bash
# Reduce memory usage (may impact performance)
--gpu-memory-utilization 0.8

# Enable CPU offloading for larger models
--cpu-offload-gb 4
```

### Batch Size Tuning

```bash
# Increase throughput for multiple concurrent requests
--max-num-batched-tokens 8192
--max-num-seqs 256
```

### Context Length

```bash
# Adjust based on your use case
--max-model-len 4096   # Shorter context, faster
--max-model-len 16384  # Longer context, more memory
```

## Running as a Service

### Linux (systemd)

Create `/etc/systemd/system/vllm.service`:

```ini
[Unit]
Description=vLLM Server for Qwen Models
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username
ExecStart=/home/your_username/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype auto \
  --max-model-len 8192
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable vllm
sudo systemctl start vllm
sudo systemctl status vllm
```

### Windows (NSSM)

1. Download NSSM: https://nssm.cc/download
2. Install service:
```cmd
nssm install vllm "C:\path\to\vllm-env\Scripts\python.exe" "-m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-Coder-32B-Instruct --host 0.0.0.0 --port 8001"
nssm start vllm
```

## Monitoring

### Check Server Logs

```bash
# View real-time logs
tail -f vllm.log

# Check for errors
grep ERROR vllm.log
```

### Monitor GPU Usage

```bash
# NVIDIA GPU monitoring
watch -n 1 nvidia-smi

# Detailed metrics
nvidia-smi dmon -s pucvmet
```

### API Health Check

```bash
# Test completion endpoint
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }'
```

## Troubleshooting

### Out of Memory Errors

```bash
# Reduce GPU memory utilization
--gpu-memory-utilization 0.7

# Use smaller model
--model Qwen/Qwen2.5-Coder-14B-Instruct

# Enable CPU offloading
--cpu-offload-gb 8
```

### Slow Inference

```bash
# Enable FP16 (if not already)
--dtype float16

# Increase batch size
--max-num-batched-tokens 16384

# Use tensor parallelism (multi-GPU)
--tensor-parallel-size 2
```

### Connection Refused

```bash
# Check if server is running
curl http://localhost:8001/health

# Check firewall
sudo ufw allow 8001

# Verify port binding
netstat -tulpn | grep 8001
```

## Alternative Models

### DeepSeek-Coder-V2

```bash
python -m vllm.entrypoints.openai.api_server \
  --model deepseek-ai/DeepSeek-Coder-V2-Instruct \
  --port 8001
```

### CodeLlama

```bash
python -m vllm.entrypoints.openai.api_server \
  --model codellama/CodeLlama-34b-Instruct-hf \
  --port 8001
```

### StarCoder2

```bash
python -m vllm.entrypoints.openai.api_server \
  --model bigcode/starcoder2-15b \
  --port 8001
```

## Cost Comparison

### vLLM (Local)
- **Setup Cost**: GPU hardware ($500-$2000)
- **Running Cost**: Electricity (~$0.10-0.30/hour)
- **Monthly Cost**: ~$75-225 (24/7 operation)

### OpenAI GPT-4
- **Setup Cost**: $0
- **Running Cost**: $0.03/1K tokens (input) + $0.06/1K tokens (output)
- **Monthly Cost**: $500-2000+ (depending on usage)

### Anthropic Claude
- **Setup Cost**: $0
- **Running Cost**: $0.015/1K tokens (input) + $0.075/1K tokens (output)
- **Monthly Cost**: $300-1500+ (depending on usage)

**Conclusion**: vLLM pays for itself within 1-3 months for moderate to heavy usage.

## Next Steps

1. Start vLLM server with your chosen model
2. Update `.env` configuration
3. Test integration with `python -m foundry.llm.test`
4. Proceed with agent implementation (Task 2)

## Support

For vLLM issues:
- GitHub: https://github.com/vllm-project/vllm
- Documentation: https://docs.vllm.ai/

For Qwen model issues:
- GitHub: https://github.com/QwenLM/Qwen2.5-Coder
- Hugging Face: https://huggingface.co/Qwen
