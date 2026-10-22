FROM python:3.11-slim-bookworm

COPY requirements.txt /opt/openrca/requirements.txt
RUN pip install --no-cache-dir -r /opt/openrca/requirements.txt \
    && mkdir -p /workspace /opt/openrca
COPY worker.py /opt/openrca/worker.py

USER 65534:65534
WORKDIR /workspace
ENTRYPOINT ["python", "-I", "-u", "/opt/openrca/worker.py"]
