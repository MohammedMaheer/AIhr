ARG APP_IMAGE
FROM ${APP_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara antiword libreoffice-writer qpdf mupdf-tools \
    fonts-liberation2 fonts-dejavu-core fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/vps/preview/worker.py /maintenance/word_converter.py
ENV PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
USER appuser
