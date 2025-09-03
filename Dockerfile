FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for volumes
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "tennis-scheduler/main.py"]