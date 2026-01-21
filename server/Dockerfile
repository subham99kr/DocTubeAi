FROM python:3.11-slim

# --------------------
# System environment
# --------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# --------------------
# System dependencies (OCR + PDF)
# --------------------
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libgl1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --------------------
# Install ML deps FIRST (critical)
# --------------------
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir \
    sentence-transformers \
    transformers \
    scikit-learn \
    scipy \
    numpy

# --------------------
# Install remaining Python deps
# --------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --------------------
# Copy application code
# --------------------
COPY . .

# --------------------
# Expose FastAPI port
# --------------------
EXPOSE 8000

# --------------------
# Run server
# --------------------
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

