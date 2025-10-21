FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8080

# 启动服务
CMD ["python", "pc28_service_optimized.py"]
