FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/triage/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY . /app
RUN mkdir -p /app/runtime
ENV SQLITE_PATH=/app/runtime/acadza.sqlite3
EXPOSE 8000
WORKDIR /app/services/triage
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1"]
