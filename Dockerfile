FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for lxml
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.104.0 \
    uvicorn[standard]>=0.24.0 \
    pandas>=2.0.0 \
    openpyxl>=3.0.0 \
    httpx>=0.25.0 \
    beautifulsoup4>=4.12.0 \
    lxml>=4.9.0 \
    jinja2>=3.1.0 \
    python-multipart>=0.0.6 \
    itsdangerous>=2.1.0 \
    python-dotenv>=1.0.0

# Copy application code
COPY . .

# Create cache directory
RUN mkdir -p /app/cache

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
