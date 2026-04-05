# Configuration Reference

## Configuration Files

Settings are loaded in this order (later overrides earlier):
1. `config/settings.yaml` — base defaults
2. `config/settings.{APP_ENV}.yaml` — environment override
3. `.env` file — environment variables (highest priority)

## Key Settings

### Agents

```yaml
agents:
  planning:
    model: claude-sonnet-4-6
    temperature: 0.1
    max_tokens: 4096
    timeout_seconds: 60
  research:
    model: claude-haiku-4-5-20251001
    temperature: 0.3
    max_tokens: 2048
  execution:
    model: claude-sonnet-4-6
    temperature: 0.2
    max_tokens: 4096
  validation:
    model: claude-haiku-4-5-20251001
    temperature: 0.1
    max_tokens: 1024
```

### Orchestrator

```yaml
orchestrator:
  max_concurrent_agents: 10
  request_timeout_seconds: 300
  max_retries: 3
  retry_delay_seconds: 1
```

### Inference

```yaml
inference:
  provider: anthropic  # anthropic | openai | vllm
  vllm:
    host: localhost
    port: 8080
    tensor_parallel_size: 4
    gpu_memory_utilization: 0.90
    max_batch_size: 32
  dynamo:
    enabled: false  # Enable PyTorch Dynamo compilation
```

### Cost Tracking

```yaml
costs:
  input_cost_per_1k_tokens: 0.003
  output_cost_per_1k_tokens: 0.015
  budget_alert_threshold_usd: 10.0
```

## Environment Variables

All settings can be overridden via environment variables.

```bash
# Core
APP_ENV=production
APP_PORT=8000
LOG_LEVEL=WARNING

# AI
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_MODEL=claude-sonnet-4-6

# Storage
REDIS_HOST=redis-service
POSTGRES_HOST=postgres-service
POSTGRES_PASSWORD=secure-password

# Inference
VLLM_HOST=vllm-service
VLLM_PORT=8080
```
