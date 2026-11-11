ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache tzdata ca-certificates

# Bare Python-standardbiblioteket – ingen pakker å installere
COPY app /app
WORKDIR /app

CMD ["python3", "-u", "/app/main.py"]
