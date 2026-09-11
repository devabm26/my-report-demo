FROM python:3.11

WORKDIR /app

# Copy dependency manifest first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app.py .
COPY templates/ templates/

EXPOSE 8080

CMD ["python", "app.py"]
