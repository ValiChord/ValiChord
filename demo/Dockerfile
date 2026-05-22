FROM python:3.12-slim
WORKDIR /app

COPY demo/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY demo/ /app/demo/

WORKDIR /app/demo
ENV PORT=8080
EXPOSE 8080

CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180 app:app
