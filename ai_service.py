#!/usr/bin/env python3
import asyncio
import aiohttp
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import secretmanager
import uvicorn

app = FastAPI(title="PC28 Navigator AI Service")

class AIRequest(BaseModel):
    task: str
    model: str = "openai/gpt-5-2025-08-07"
    max_tokens: int = 2000

class AIService:
    def __init__(self):
        self.api_key = self.get_secret("aiml-api-key")
        
    def get_secret(self, secret_id):
        client = secretmanager.SecretManagerServiceClient()
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    
    async def call_ai_model(self, request: AIRequest):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": request.model,
            "messages": [
                {"role": "user", "content": request.task}
            ],
            "max_tokens": request.max_tokens,
            "temperature": 0.1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.aimlapi.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise HTTPException(status_code=response.status)

ai_service = AIService()

@app.post("/analyze")
async def analyze(request: AIRequest):
    """AI分析接口"""
    result = await ai_service.call_ai_model(request)
    return result

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "PC28 Navigator AI"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
