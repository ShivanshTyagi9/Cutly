FROM python:3.11-slim

RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/setup.sh

EXPOSE 5000
ENV PYTHONUNBUFFERED=1
CMD ["/app/setup.sh"]
