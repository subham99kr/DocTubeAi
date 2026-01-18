FROM python:3.11-slim

# --- System environment ---
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (OCR + PDF)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    && rm -rf /var/lib/apt/lists/* 


# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code 
COPY . .

# Exposeing FastAPI port
EXPOSE 8000

# --- Run server ---
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
