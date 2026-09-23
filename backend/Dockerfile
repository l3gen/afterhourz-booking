# syntax=docker/dockerfile:1
FROM python:3.14-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt \
 && /opt/venv/bin/pip uninstall -y setuptools wheel

FROM python:3.14-slim
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# The runtime needs no packaging tools. Removing pip/setuptools/wheel drops their vendored
# libraries, which is where Trivy keeps finding fixable HIGH CVEs in the base image.
RUN /usr/local/bin/python -m pip uninstall -y setuptools wheel pip \
 && useradd --system --uid 10001 --no-create-home app
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status==200 else 1)"
# ALB terminates the connection from CloudFront; trust its X-Forwarded-* headers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
