FROM python:3.11-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN addgroup --system app && adduser --system --ingroup app app

COPY --chown=app:app setup.py /app/
COPY --chown=app:app skincarelib /app/skincarelib
COPY --chown=app:app features /app/features
COPY --chown=app:app artifacts /app/artifacts
COPY --chown=app:app scripts /app/scripts
COPY --chown=app:app docs /app/docs

RUN python -m pip install --upgrade pip \
    && pip install -e .

USER app

CMD ["python", "scripts/run_evaluation.py"]
