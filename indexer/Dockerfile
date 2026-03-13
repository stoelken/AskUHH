FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3.11 /usr/bin/python

WORKDIR /indexer

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Pre-download CLIP model during build to avoid cold start
RUN python3 -c "from transformers import CLIPModel, CLIPProcessor; CLIPModel.from_pretrained('openai/clip-vit-base-patch32'); CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')"

COPY app/ ./app/

RUN mkdir -p /data/chroma_db /data/images

EXPOSE 8500

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8500"]
