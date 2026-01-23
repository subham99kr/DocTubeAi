FROM python:3.11-alpine

# System dependencies (for SSL & requests stability)
RUN apk add --no-cache \
    ca-certificates \
    gcc \
    musl-dev

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
