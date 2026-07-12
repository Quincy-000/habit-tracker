FROM python:3.12-slim-bookworm

WORKDIR /app

# Patch OS-level packages to close known, fixable CVEs
RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tracker.py .
COPY templates ./templates

EXPOSE 5000
CMD ["python", "tracker.py", "web"]
