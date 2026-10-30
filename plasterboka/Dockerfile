ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache tzdata

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /app
WORKDIR /app

CMD ["python3", "-u", "/app/main.py"]
