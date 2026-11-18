FROM python:3.13-slim
RUN pip install --no-cache-dir pytest requests pillow
WORKDIR /workspace
