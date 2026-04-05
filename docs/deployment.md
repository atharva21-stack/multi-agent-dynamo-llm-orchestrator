# Deployment Guide

## Docker Deployment (Recommended for Development)

```bash
# Build images
make docker-build

# Start all services
make docker-up

# Check status
docker-compose -f docker/docker-compose.yml ps

# View logs
make docker-logs

# Stop
make docker-down
```

## Kubernetes Deployment

### Prerequisites
- kubectl configured for your cluster
- Container images pushed to registry

### Deploy

```bash
# Create namespace
kubectl apply -f kubernetes/namespace.yaml

# Apply ConfigMap
kubectl apply -f kubernetes/configmap.yaml

# Create secrets (edit first!)
# kubectl create secret generic api-secrets \
#   --from-literal=anthropic-api-key=YOUR_KEY \
#   -n agent-inference-stack

# Deploy services
kubectl apply -f kubernetes/redis.yaml
kubectl apply -f kubernetes/postgres.yaml
kubectl apply -f kubernetes/api-gateway.yaml
kubectl apply -f kubernetes/ingress.yaml
kubectl apply -f kubernetes/hpa.yaml

# Check deployment
kubectl get pods -n agent-inference-stack
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `REDIS_HOST` | No | localhost | Redis hostname |
| `POSTGRES_HOST` | No | localhost | PostgreSQL hostname |
| `APP_ENV` | No | development | Environment name |
| `LOG_LEVEL` | No | INFO | Logging verbosity |

See [.env.example](../.env.example) for the full list.

## GPU Deployment (vLLM)

For local inference with vLLM:
```bash
# Requires NVIDIA GPU + Docker with GPU support
docker build -f docker/Dockerfile.vllm -t agent-vllm .
docker run --gpus all -p 8080:8080 \
  -e VLLM_MODEL=meta-llama/Llama-2-70b-chat-hf \
  -e TENSOR_PARALLEL_SIZE=4 \
  agent-vllm
```

Then set in `.env`:
```bash
VLLM_HOST=localhost
VLLM_PORT=8080
```

## Monitoring

```bash
# Prometheus metrics
curl http://localhost:9090/metrics

# Health check
curl http://localhost:8000/api/v1/health
```
