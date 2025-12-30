# Deploying LangChain RAG Application to Google Cloud with Kubernetes

This guide will help you deploy your Dockerized LangChain RAG application to Google Cloud Platform using Google Kubernetes Engine (GKE).

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and configured
3. **kubectl** installed
4. **Docker** installed
5. Your application already containerized with Docker Compose

## Quick Deployment

### 1. Configure Deployment Script

Edit `deploy-gcp.sh` and update these variables:
```bash
PROJECT_ID="your-gcp-project-id"
CLUSTER_NAME="rag-cluster"
REGION="us-central1"
DOMAIN="your-domain.com"  # Optional
STATIC_IP_NAME="rag-app-ip"  # Optional
```

### 2. Update Kubernetes Manifests

Update the image references in:
- `k8s/backend-deployment.yaml`
- `k8s/frontend-deployment.yaml`

Replace `YOUR_PROJECT_ID` with your actual GCP project ID.

### 3. Update Secrets

Update `k8s/secret.yaml` with your actual base64-encoded environment variables:

```bash
# Encode your secrets
echo -n "your-groq-api-key" | base64
echo -n "your-secret-key" | base64
```

### 4. Run Deployment

```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

## Manual Deployment Steps

If you prefer to deploy manually:

### 1. Set up Google Cloud Project

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable container.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 2. Build and Push Images

```bash
# Backend
cd backend
docker build -t gcr.io/YOUR_PROJECT_ID/rag-backend:latest .
docker push gcr.io/YOUR_PROJECT_ID/rag-backend:latest

# Frontend
cd ../frontend
docker build -t gcr.io/YOUR_PROJECT_ID/rag-frontend:latest .
docker push gcr.io/YOUR_PROJECT_ID/rag-frontend:latest
```

### 3. Create GKE Cluster

```bash
gcloud container clusters create rag-cluster \
    --region=us-central1 \
    --num-nodes=3 \
    --machine-type=e2-medium \
    --enable-autoscaling \
    --min-nodes=1 \
    --max-nodes=5
```

### 4. Deploy to Kubernetes

```bash
# Get cluster credentials
gcloud container clusters get-credentials rag-cluster --region=us-central1

# Deploy all resources
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -n rag-app
kubectl get services -n rag-app
kubectl get ingress -n rag-app
```

## Architecture Overview

```
Internet
    ↓
[Google Cloud Load Balancer]
    ↓
[Kubernetes Ingress]
    ↓
├── [Frontend Service] → [Frontend Pods (Nginx)]
└── [Backend Service] → [Backend Pods (FastAPI)]
                          ↓
                   [Persistent Volumes]
                   ├── /app/data (PVC)
                   └── /app/vectorstore (PVC)
```

## Configuration Details

### Resources
- **Backend**: 512Mi-1Gi RAM, 250m-500m CPU
- **Frontend**: 128Mi-256Mi RAM, 100m-200m CPU
- **Storage**: 10Gi for data, 20Gi for vectorstore

### Networking
- Frontend accessible on port 80
- Backend accessible internally on port 8000
- API routes proxied through `/api/*`

### Security
- Secrets stored in Kubernetes Secrets
- Environment variables injected at runtime
- CORS configured for container communication

## Monitoring and Maintenance

### Check Application Health

```bash
# Check pod status
kubectl get pods -n rag-app

# Check logs
kubectl logs -f deployment/rag-backend -n rag-app
kubectl logs -f deployment/rag-frontend -n rag-app

# Check resource usage
kubectl top pods -n rag-app
```

### Scaling

```bash
# Scale backend
kubectl scale deployment rag-backend --replicas=3 -n rag-app

# Scale frontend
kubectl scale deployment rag-frontend --replicas=3 -n rag-app
```

### Updates

```bash
# Update images
kubectl set image deployment/rag-backend backend=gcr.io/YOUR_PROJECT_ID/rag-backend:v2 -n rag-app
kubectl set image deployment/rag-frontend frontend=gcr.io/YOUR_PROJECT_ID/rag-frontend:v2 -n rag-app

# Rolling restart
kubectl rollout restart deployment/rag-backend -n rag-app
kubectl rollout restart deployment/rag-frontend -n rag-app
```

## Cost Optimization

1. **Use appropriate machine types**: e2-medium for development/small scale
2. **Enable autoscaling**: Automatically scale based on load
3. **Use preemptible VMs**: For non-critical workloads (not recommended for production)
4. **Monitor resource usage**: Adjust resource requests/limits based on actual usage

## Troubleshooting

### Common Issues

1. **Image pull errors**: Ensure images are pushed to GCR and accessible
2. **Pod crashes**: Check logs with `kubectl logs`
3. **Service unreachable**: Verify service selectors and ports
4. **Ingress not working**: Check ingress controller and firewall rules

### Useful Commands

```bash
# Debug networking
kubectl exec -it <pod-name> -n rag-app -- /bin/bash

# Port forward for testing
kubectl port-forward svc/rag-backend-service 8000:8000 -n rag-app

# Check events
kubectl get events -n rag-app --sort-by=.metadata.creationTimestamp
```

## Security Best Practices

1. **Use managed certificates** for SSL/TLS
2. **Implement proper RBAC** for Kubernetes access
3. **Regularly update** base images and dependencies
4. **Monitor logs** for security events
5. **Use secrets** for sensitive data (not ConfigMaps)

## Next Steps

1. Set up monitoring with Google Cloud Monitoring
2. Configure logging with Cloud Logging
3. Set up CI/CD pipeline with Cloud Build
4. Implement backup strategy for persistent data
5. Configure auto-scaling based on custom metrics