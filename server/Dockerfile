FROM python:3.11-slim

# --------------------
# Environment
# --------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

# --------------------
# System dependencies
# --------------------
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    ffmpeg \
    libgl1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# --------------------
# Python dependencies
# --------------------
COPY requirements.txt .

# CPU-only PyTorch
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir \
    transformers==4.38.2 \
    scikit-learn \
    scipy \
    numpy

RUN pip install --no-cache-dir -r requirements.txt

# Remove compiler after packages are built
RUN apt-get purge -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# --------------------
# Application
# --------------------
COPY . .

# --------------------
# Hugging Face Spaces
# --------------------
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]