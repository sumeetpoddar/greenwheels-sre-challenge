
# --------------------------------------------------
# BASE IMAGE
# --------------------------------------------------

FROM python:3.12-slim

# --------------------------------------------------
# ENVIRONMENT CONFIGURATION
# --------------------------------------------------

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# --------------------------------------------------
# WORKING DIRECTORY
# --------------------------------------------------

WORKDIR /app

# --------------------------------------------------
# CREATE NON-ROOT USER
# --------------------------------------------------

RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --create-home appuser

# --------------------------------------------------
# INSTALL PYTHON DEPENDENCIES
# --------------------------------------------------

COPY requirements.txt .

RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt

# --------------------------------------------------
# COPY APPLICATION SOURCE CODE
# --------------------------------------------------

COPY app/ ./app/

# --------------------------------------------------
# SECURITY: RUN AS NON-ROOT USER
# --------------------------------------------------

USER appuser

# --------------------------------------------------
# EXPOSE APPLICATION PORT
# --------------------------------------------------

EXPOSE 8000

# --------------------------------------------------
# APPLICATION STARTUP
# --------------------------------------------------

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
