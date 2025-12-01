# Simple Dockerfile for FastAPI backend
# Build: docker build -t clinic-backend ./backend
# Run (local): docker run -p 8000:8000 --env-file ../.env clinic-backend

FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app

ENV HOST=0.0.0.0
ENV PORT=8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
