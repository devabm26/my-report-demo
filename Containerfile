FROM python:3.12-slim

# Non-root user for OpenShift compatibility (arbitrary UID)
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /sbin/nologin appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/

# OpenShift runs containers with a random UID in group 0 — ensure group-writable
RUN chown -R 1001:0 /app && chmod -R g=u /app

USER 1001

EXPOSE 8080

CMD ["python", "app.py"]
