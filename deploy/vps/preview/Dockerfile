FROM python:3.11-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer fonts-liberation2 fonts-dejavu-core fonts-noto-core \
    fonts-crosextra-carlito fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 999 appuser && useradd --uid 999 --gid 999 --no-create-home appuser
COPY worker.py /worker.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 999:999
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import socket; s=socket.socket(socket.AF_UNIX); s.settimeout(3); s.connect('/run/preview/renderer.sock'); s.sendall(b'GET /health HTTP/1.0\r\n\r\n'); assert b'200 OK' in s.recv(128)"
CMD ["python", "/worker.py"]
