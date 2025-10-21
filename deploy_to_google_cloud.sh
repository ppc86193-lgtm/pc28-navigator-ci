#!/bin/bash
# Google Cloud AI服务部署脚本

set -euo pipefail

PROJECT_ID="wprojectl"
REGION="us-central1"
SERVICE_NAME="pc28-navigator-ai"

echo "🚀 部署PC28 Navigator AI服务到Google Cloud"

# 1. 设置项目
gcloud config set project $PROJECT_ID

# 2. 启用必要的API
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com

# 3. 创建Secret Manager密钥
echo "🔑 创建API密钥..."
echo "9030c9fcbc474c258dca7ff39b3a20e6" | gcloud secrets create aiml-api-key --data-file=-

# 4. 构建和部署Cloud Run服务
echo "🏗️ 构建AI服务..."
gcloud run deploy $SERVICE_NAME \
  --source=. \
  --region=$REGION \
  --allow-unauthenticated \
  --set-env-vars="PROJECT_ID=wprojectl,DATASET=pc28" \
  --set-secrets="AIML_API_KEY=aiml-api-key:latest" \
  --memory=4Gi \
  --cpu=2 \
  --max-instances=100 \
  --min-instances=1

echo "✅ AI服务部署完成！"
echo "📡 服务URL: https://$SERVICE_NAME-$REGION.a.run.app"
