# LLM Configuration Guide

This document explains how to configure LLM providers for the Autonomous Software Foundry.

## Overview

The foundry supports multiple LLM providers with a flexible configuration system:

- **vLLM** (Default): Local inference with Qwen models
- **OpenAI**: GPT-4, GPT-4-turbo (optional fallback)
- **Anthropic**: Claude 3.5 Sonnet (optional fallback)

## Default Configuration: vLLM + Qwen

### Why Qwen2.5-Coder?

- **State-of-the-art**: Top performance on code generation benchmarks
- **Cost-effective**: No API costs, runs locally
- **Privacy**: All data stays on your infrastructure
- **Customizable**: Full control over inference parameters
- **Multiple sizes**: 7B, 14B, 32B models for different hardware

### Recommended Models by Agent

| Agent | Recommended Model | VRAM | Purpose |
|-------|------------------|------|---------|
| Product Manager | Qwen2.5-Coder-32B-Instruct | 24GB | Requirements analysis, PRD generation |
| Architect | Qwen2.5-Coder-32B-Instruct | 24GB | System design, architecture decisions |
| Engineering | Qwen2.5-Coder-32B-Instruct | 24GB | Code generation, implementation |
| DevOps | Qwen2.5-Coder-32B-Instruct | 24GB | Infrastructure code, CDK generation |
| Reflexion Engine | Qwen2.5-Coder-14B-Instruct | 12GB | Fast error correction, iteration |
| Code Review | Qwen2.5-Coder-32B-Instruct | 24GB | Quality analysis, security scanning |

### Configuration

Edit `.env`:

```bash
# vLLM Configuration
VLLM_BASE_URL=http://localhost:8001/v1
VLLM_API_KEY=EMPTY
VLLM_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct
DEFAULT_LLM_PROVIDER=vllm
```

### Starting vLLM Server

```bash
# 32B model (recommended)
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-32B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype auto \
  --max-model-len 8192

# 14B model (budget option)
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-Coder-14B-Instruct \
  --host 0.0.0.0 \
  --port 8001 \
  --dtype auto \
  --max-model-len 8192
```

## Alternative: OpenAI (Fallback)

### Configuration

```bash
# .env
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL_NAME=gpt-4-turbo-preview
```

### Cost Considerations

- GPT-4: $0.03/1K input tokens, $0.06/1K output tokens
- GPT-4-turbo: $0.01/1K input tokens, $0.03/1K output tokens
- Estimated monthly cost: $500-2000+ depending on usage

## Alternative: Anthropic (Fallback)

### Configuration

```bash
# .env
DEFAULT_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022
```

### Cost Considerations

- Claude 3.5 Sonnet: $0.015/1K input tokens, $0.075/1K output tokens
- Estimated monthly cost: $300-1500+ depending on usage

## Multi-Provider Setup (Recommended)

Configure vLLM as primary with commercial providers as fallback:

```bash
# .env
DEFAULT_LLM_PROVIDER=vllm

# vLLM (primary)
VLLM_BASE_URL=http://localhost:8001/v1
VLLM_API_KEY=EMPTY
VLLM_MODEL_NAME=Qwen/Qwen2.5-Coder-32B-Instruct

# OpenAI (fallback)
OPENAI_API_KEY=sk-your-api-key-here

# Anthropic (fallback)
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

The system will automatically fall back to commercial providers if vLLM is unavailable.

## Per-Agent Model Configuration

You can configure different models for different agents:

```python
# config/agents.yaml (future feature)
agents:
  product_manager:
    provider: vllm
    model: Qwen/Qwen2.5-Coder-32B-Instruct
    temperature: 0.7
    
  architect:
    provider: vllm
    model: Qwen/Qwen2.5-Coder-32B-Instruct
    temperature: 0.5
    
  engineering:
    provider: vllm
    model: Qwen/Qwen2.5-Coder-32B-Instruct
    temperature: 0.3
    
  reflexion:
    provider: vllm
    model: Qwen/Qwen2.5-Coder-14B-Instruct  # Faster for iteration
    temperature: 0.2
```

## Testing Your Configuration

```bash
# Test vLLM connection
python -m foundry.llm.test

# Expected output:
# ✓ Created provider: vllm
# ✓ Model: Qwen/Qwen2.5-Coder-32B-Instruct
# 📝 Generating code...
# ✓ Generation complete!
```

## Performance Tuning

### Temperature Settings

- **0.0-0.3**: Deterministic, best for code generation
- **0.4-0.7**: Balanced, good for architecture and design
- **0.8-1.0**: Creative, useful for brainstorming

### Context Length

```bash
# Adjust based on your needs
--max-model-len 4096   # Shorter context, faster
--max-model-len 8192   # Balanced (recommended)
--max-model-len 16384  # Longer context, more memory
```

### Batch Size

```bash
# For higher throughput with multiple concurrent requests
--max-num-batched-tokens 8192
--max-num-seqs 256
```

## Troubleshooting

### vLLM Connection Failed

```bash
# Check if server is running
curl http://localhost:8001/v1/models

# Check logs
tail -f vllm.log
```

### Out of Memory

```bash
# Use smaller model
--model Qwen/Qwen2.5-Coder-14B-Instruct

# Reduce GPU memory utilization
--gpu-memory-utilization 0.8

# Enable CPU offloading
--cpu-offload-gb 4
```

### Slow Generation

```bash
# Enable FP16
--dtype float16

# Increase batch size
--max-num-batched-tokens 16384

# Use tensor parallelism (multi-GPU)
--tensor-parallel-size 2
```

## Cost Comparison

### vLLM (Local)
- **Hardware**: $500-2000 (one-time)
- **Electricity**: ~$75-225/month (24/7)
- **Total Year 1**: $1400-4700
- **Total Year 2+**: $900-2700/year

### OpenAI GPT-4
- **Hardware**: $0
- **API Costs**: $500-2000/month
- **Total Year 1**: $6000-24000
- **Total Year 2+**: $6000-24000/year

### Anthropic Claude
- **Hardware**: $0
- **API Costs**: $300-1500/month
- **Total Year 1**: $3600-18000
- **Total Year 2+**: $3600-18000/year

**Conclusion**: vLLM pays for itself within 1-3 months for moderate usage.

## Next Steps

1. Set up vLLM server (see [VLLM_SETUP.md](VLLM_SETUP.md))
2. Configure `.env` with your chosen provider
3. Test configuration: `python -m foundry.llm.test`
4. Proceed with agent implementation

## Support

- vLLM: https://docs.vllm.ai/
- Qwen: https://github.com/QwenLM/Qwen2.5-Coder
- OpenAI: https://platform.openai.com/docs
- Anthropic: https://docs.anthropic.com/
