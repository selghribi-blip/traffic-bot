FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libc-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create directories
RUN mkdir -p results logs

# Run as non-root
RUN useradd -m -u 1000 scrapy && chown -R scrapy:scrapy /app
USER scrapy

CMD ["scrapy", "crawl", "traffic_bot"]