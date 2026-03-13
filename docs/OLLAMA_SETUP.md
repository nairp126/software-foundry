# Ollama Setup Guide for Qwen Models

This guide explains how to set up Ollama to serve Qwen coding models locally for the Autonomous Software Foundry.

## Why Ollama + Qwen?

- **Windows Native**: Full Windows support, no WSL2 required
- **Easy Setup**: 5-minute installation
- **Cost-Effective**: No API costs, runs on your hardware
- **Privacy**: All data stays local
- **Good Performance**: Optimized inference with quantization
- **Quality**: Qwen2.5-Coder models are excellent for code generation

## Prerequisites

- Windows 10/11, macOS, or Linux
- NVIDIA GPU with 8GB+ VRAM (recommended) or CPU (slower)
- 10GB+ free disk space for model weights

## Installation

### Windows

1. **Download Ollama**
   - Visit: https://ollama.com/download/windows
   - Download the installer
   - Run `OllamaSetup.exe`

2. **Verify Installation**
   ```powershell
   ollama --version
   ```

### macOS

```bash
# Using Homebrew
brew install ollama

# Or download from https://ollama.com/download/mac
```

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## Quick Start

### 1. Pull Qwen Model

```bash
# Qwen2.5-Coder 7B (Recommended for testing/development)
ollama pull qwen2.5-coder:7b

# Alternative sizes:
# ollama pull qwen2.5-coder:1.5b  # Lightweight (2GB VRAM)
# ollama pull qwen2.5-coder:14b   # Balanced (12GB VRAM)
# ollama pull qwen2.5-coder:32b   # Best quality (24GB VRAM)
```

### 2. Test the Model

```bash
# Interactive chat
ollama run qwen2.5-coder:7b

# Test with a coding question
>>> Write a Python function to calculate fibonacci numbers
```

Press `Ctrl+D` or type `/bye` to exit.

### 3. Verify API Server

Ollama automatically starts an API server on `http://localhost:11434`

```bash
# Test API
curl http://localhost:11434/api/tags
```

Expected output:
```json
{
  "models": [
    {
      "name": "qwen2.5-coder:7b",
      "modified_at": "2024-01-15T10:30:00Z",
      "size": 4661211648
    }
  ]
}
```

## Configuration

### Update Foundry Configuration

Edit your `.env` file:

```bash
# Ollama Configuration (Primary)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=qwen2.5-coder:7b
DEFAULT_LLM_PROVIDER=ollama
```

### Test Integration

```bash
# Activate your foundry environment
# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate

# Test Ollama provider
python -m foundry.llm.test
```

Expected output:
```
Testing Ollama Provider with Qwen Model
==================================================
✓ Created provider: ollama
✓ Model: qwen2.5-coder:7b

📝 Generating code...

✓ Generation complete!
  Model: qwen2.5-coder:7b
  Tokens used: 234
  Finish reason: stop

📄 Generated code:
[Python code output]

✓ All tests passed!
```

## Model Comparison

### Qwen2.5-Coder-7B (Recommended for Development)

- **VRAM**: 8GB
- **Disk**: 4.7GB
- **Speed**: ~30-50 tokens/second (GPU)
- **Quality**: Excellent for most coding tasks
- **Use Case**: Development, testing, rapid iteration

**Pull command:**
```bash
ollama pull qwen2.5-coder:7b
```

### Qwen2.5-Coder-1.5B (Lightweight)

- **VRAM**: 2GB
- **Disk**: 1.5GB
- **Speed**: ~50-80 tokens/second (GPU)
- **Quality**: Good for simple tasks
- **Use Case**: Quick testing, resource-constrained environments

**Pull command:**
```bash
ollama pull qwen2.5-coder:1.5b
```

### Qwen2.5-Coder-14B (Balanced)

- **VRAM**: 12GB
- **Disk**: 9GB
- **Speed**: ~20-40 tokens/second (GPU)
- **Quality**: Very good, better reasoning
- **Use Case**: Production, complex code generation

**Pull command:**
```bash
ollama pull qwen2.5-coder:14b
```

### Qwen2.5-Coder-32B (Best Quality)

- **VRAM**: 24GB
- **Disk**: 19GB
- **Speed**: ~10-20 tokens/second (GPU)
- **Quality**: Excellent, best reasoning
- **Use Case**: Production, critical applications

**Pull command:**
```bash
ollama pull qwen2.5-coder:32b
```

## Advanced Configuration

### Custom Model Parameters

Create a `Modelfile`:

```dockerfile
FROM qwen2.5-coder:7b

# Set temperature
PARAMETER temperature 0.3

# Set context window
PARAMETER num_ctx 8192

# Set top-p sampling
PARAMETER top_p 0.9

# Set system prompt
SYSTEM You are an expert software engineer specializing in clean, maintainable code.
```

Create custom model:
```bash
ollama create qwen-foundry -f Modelfile
```

Update `.env`:
```bash
OLLAMA_MODEL_NAME=qwen-foundry
```

### GPU Configuration

Ollama automatically uses GPU if available. To force CPU:

```bash
# Windows
set OLLAMA_NUM_GPU=0
ollama serve

# Linux/Mac
OLLAMA_NUM_GPU=0 ollama serve
```

### Memory Management

```bash
# Limit GPU memory usage (in GB)
# Windows
set OLLAMA_GPU_MEMORY_FRACTION=0.8

# Linux/Mac
export OLLAMA_GPU_MEMORY_FRACTION=0.8
```

## Running as a Service

### Windows

Ollama automatically installs as a Windows service and starts on boot.

**Manage service:**
```powershell
# Check status
Get-Service Ollama

# Restart service
Restart-Service Ollama

# Stop service
Stop-Service Ollama

# Start service
Start-Service Ollama
```

### Linux (systemd)

```bash
# Enable service
sudo systemctl enable ollama

# Start service
sudo systemctl start ollama

# Check status
sudo systemctl status ollama

# View logs
journalctl -u ollama -f
```

### macOS

```bash
# Start Ollama
ollama serve

# Or use launchd for automatic startup
# Create ~/Library/LaunchAgents/com.ollama.ollama.plist
```

## Performance Tuning

### Optimize for Speed

```bash
# Use smaller model
ollama pull qwen2.5-coder:1.5b

# Reduce context window
PARAMETER num_ctx 4096
```

### Optimize for Quality

```bash
# Use larger model
ollama pull qwen2.5-coder:14b

# Lower temperature for more deterministic output
PARAMETER temperature 0.2

# Increase context window
PARAMETER num_ctx 16384
```

### Batch Processing

For multiple requests, Ollama automatically batches them for efficiency.

## Troubleshooting

### Ollama Not Starting

```powershell
# Windows: Check if port is in use
netstat -ano | findstr :11434

# Kill process if needed
taskkill /PID <PID> /F

# Restart Ollama service
Restart-Service Ollama
```

### Model Not Found

```bash
# List installed models
ollama list

# Pull model again
ollama pull qwen2.5-coder:7b
```

### Slow Performance

```bash
# Check GPU usage
# Windows: Task Manager > Performance > GPU
# Linux: nvidia-smi

# Verify GPU is being used
ollama ps

# If using CPU, check GPU drivers
nvidia-smi
```

### Out of Memory

```bash
# Use smaller model
ollama pull qwen2.5-coder:1.5b

# Or reduce context window
# Edit Modelfile:
PARAMETER num_ctx 2048
```

### Connection Refused

```bash
# Check if Ollama is running
# Windows:
Get-Service Ollama

# Linux:
systemctl status ollama

# Test connection
curl http://localhost:11434/api/tags
```

## API Usage Examples

### Chat Completion

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "qwen2.5-coder:7b",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful coding assistant."
    },
    {
      "role": "user",
      "content": "Write a Python function to reverse a string."
    }
  ]
}'
```

### Streaming Response

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "qwen2.5-coder:7b",
  "messages": [
    {"role": "user", "content": "Explain recursion"}
  ],
  "stream": true
}'
```

### Generate (Simple)

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5-coder:7b",
  "prompt": "Write a hello world program in Python"
}'
```

## Cost Comparison

### Ollama (Local)
- **Hardware**: $0-500 (if GPU upgrade needed)
- **Electricity**: ~$0.05-0.15/hour (GPU operation)
- **Monthly**: ~$35-110 (24/7 operation)
- **Total Year 1**: $35-610

### OpenAI GPT-4
- **Hardware**: $0
- **API Costs**: $500-2000/month
- **Total Year 1**: $6000-24000

**Conclusion**: Ollama is the most cost-effective solution, especially for Windows users.

## Upgrading Models

```bash
# Check for updates
ollama list

# Pull latest version
ollama pull qwen2.5-coder:7b

# Remove old versions
ollama rm qwen2.5-coder:7b-old
```

## Uninstallation

### Windows

```powershell
# Uninstall via Settings > Apps
# Or use installer to uninstall

# Remove models (optional)
Remove-Item -Recurse -Force $env:USERPROFILE\.ollama
```

### Linux

```bash
# Stop service
sudo systemctl stop ollama
sudo systemctl disable ollama

# Remove Ollama
sudo rm /usr/local/bin/ollama
sudo rm /etc/systemd/system/ollama.service

# Remove models (optional)
rm -rf ~/.ollama
```

## Next Steps

1. **Verify Installation**: `ollama list`
2. **Update Configuration**: Edit `.env` file
3. **Test Integration**: `python -m foundry.llm.test`
4. **Proceed with Development**: Continue with Task 2 (Agent Orchestration)

## Additional Resources

- Ollama Documentation: https://github.com/ollama/ollama
- Qwen Models: https://huggingface.co/Qwen
- Ollama Model Library: https://ollama.com/library
- Community Discord: https://discord.gg/ollama

## Support

For issues:
1. Check troubleshooting section above
2. Review Ollama GitHub issues: https://github.com/ollama/ollama/issues
3. Check Qwen documentation: https://github.com/QwenLM/Qwen2.5-Coder
