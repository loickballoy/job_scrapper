FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gradjobs/ gradjobs/

# Volume pour persister la base SQLite entre les runs/redéploiements
VOLUME ["/app/data"]

CMD ["python3", "-m", "gradjobs", "run"]