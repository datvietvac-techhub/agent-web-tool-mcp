FROM python:3.12-slim

WORKDIR /app

COPY mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp/server.py mcp/api.py mcp/tools.py mcp/url_policy.py ./
COPY mcp/providers/ ./providers/
COPY config/providers.yaml.example ./config/providers.yaml

EXPOSE 8000

CMD ["python", "server.py"]
