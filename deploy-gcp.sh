#!/bin/bash

# Google Cloud RAG Application Deployment Script
# Make sure to update the variables below before running

# Configuration - UPDATE THESE VALUES
PROJECT_ID="your-gcp-project-id"
CLUSTER_NAME="rag-cluster"
REGION="us-central1"
DOMAIN="your-domain.com"  # Optional
STATIC_IP_NAME="rag-app-ip"  # Optional

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting RAG Application Deployment to Google Cloud${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Authenticate and set project
echo -e "${YELLOW}🔐 Authenticating with Google Cloud...${NC}"
gcloud auth login
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "${YELLOW}🔧 Enabling required APIs...${NC}"
gcloud services enable container.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable compute.googleapis.com

# Build and push Docker images
echo -e "${YELLOW}🐳 Building and pushing Docker images...${NC}"

# Build backend image
cd backend
docker build -t gcr.io/$PROJECT_ID/rag-backend:latest .
docker push gcr.io/$PROJECT_ID/rag-backend:latest

# Build frontend image
cd ../frontend
docker build -t gcr.io/$PROJECT_ID/rag-frontend:latest .
docker push gcr.io/$PROJECT_ID/rag-frontend:latest

cd ..

# Create GKE cluster (if it doesn't exist)
echo -e "${YELLOW}☸️  Creating GKE cluster...${NC}"
gcloud container clusters create $CLUSTER_NAME \
    --region=$REGION \
    --num-nodes=3 \
    --machine-type=e2-medium \
    --enable-autoscaling \
    --min-nodes=1 \
    --max-nodes=5

# Get cluster credentials
gcloud container clusters get-credentials $CLUSTER_NAME --region=$REGION

# Update Kubernetes manifests with your project ID
echo -e "${YELLOW}📝 Updating Kubernetes manifests...${NC}"
sed -i "s/YOUR_PROJECT_ID/$PROJECT_ID/g" k8s/backend-deployment.yaml
sed -i "s/YOUR_PROJECT_ID/$PROJECT_ID/g" k8s/frontend-deployment.yaml

# Optional: Reserve static IP (uncomment if needed)
# echo -e "${YELLOW}🌐 Reserving static IP...${NC}"
# gcloud compute addresses create $STATIC_IP_NAME --global
# STATIC_IP=$(gcloud compute addresses describe $STATIC_IP_NAME --global --format="value(address)")
# echo -e "${GREEN}Static IP reserved: $STATIC_IP${NC}"

# Optional: Create managed SSL certificate (uncomment if needed)
# echo -e "${YELLOW}🔒 Creating managed SSL certificate...${NC}"
# gcloud compute ssl-certificates create rag-app-cert \
#     --domains=$DOMAIN \
#     --global

# Deploy to Kubernetes
echo -e "${YELLOW}🚀 Deploying to Kubernetes...${NC}"

# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
kubectl apply -f k8s/ingress.yaml

# Wait for deployments to be ready
echo -e "${YELLOW}⏳ Waiting for deployments to be ready...${NC}"
kubectl wait --for=condition=available --timeout=300s deployment/rag-backend -n rag-app
kubectl wait --for=condition=available --timeout=300s deployment/rag-frontend -n rag-app

# Get service URLs
echo -e "${GREEN}✅ Deployment completed!${NC}"
echo -e "${GREEN}📊 Getting service information...${NC}"

# Get ingress IP
kubectl get ingress rag-app-ingress -n rag-app

echo -e "${GREEN}🎉 Your RAG application is now deployed!${NC}"
echo -e "${YELLOW}Note: It may take a few minutes for the load balancer to be fully ready.${NC}"