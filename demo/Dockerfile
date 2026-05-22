FROM python:3.12-slim
WORKDIR /app

COPY demo/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY demo/app.py demo/demo_runner.py /app/demo/
COPY demo/synthetic_study/ /app/demo/synthetic_study/

RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

WORKDIR /app/demo
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180 app:app"]
