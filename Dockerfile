FROM python:3.12.0-slim-bookworm
MAINTAINER Viktor Hronec <zamr666@gmail.com>

LABEL meta.service="freeq-server"
LABEL meta.repo="https://github.com/hronecviktor/freeq-server"

ARG DEBIAN_FRONTEND=noninteractive
ENV BUILD_DEPS="build-essential"
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt

RUN sed -r -i 's/main/main contrib/g' /etc/apt/sources.list.d/debian.sources &&\
    apt-get update && apt-get install -y debsecan && \
    # Install system-level dependencies
    apt-get install --no-install-recommends -y $BUILD_DEPS \
    $(debsecan --suite bookworm --format packages --only-fixed) && \
    pip install --upgrade pip &&\
    pip install --no-cache-dir -r requirements.txt &&\
    # Clean unnecessary packages
    apt-get remove -y $BUILD_DEPS &&\
    apt-get autoremove -y &&\
    apt-get clean &&\
    rm -rf /var/lib/apt/lists/*

COPY ./src /app/src

RUN useradd --uid 1000 --home-dir /app freeq &&\
    chown -R 1000:1000 /app
USER freeq

EXPOSE 8000/tcp
CMD ["gunicorn", \
    "--workers", \
    "4", \
    "--worker-class", \
    "uvicorn.workers.UvicornWorker", \
    "--bind", \
     "0.0.0.0:8000", \
     "--access-logfile", \
     "-", \
    "src.freeqserver.freeqserver:app" \
    ]