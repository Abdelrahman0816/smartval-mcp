FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY smartval ./smartval
RUN pip install --no-cache-dir .

COPY data ./data
ENV SMARTVAL_DATA=/app/data/products.json

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000 8001
# Default: REST API. The MCP server uses the same image with a different command.
CMD ["uvicorn", "smartval.api:app", "--host", "0.0.0.0", "--port", "8000"]
