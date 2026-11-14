FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
ENTRYPOINT ["fastapi", "run", "app.py", "--port", "5000", "--host", "0.0.0.0"]
