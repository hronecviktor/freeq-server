# FreeQ-server

---

## Server for [freeq](https://github.com/hronecviktor/freeq)
API docs @ [https://weyland.yutani.enterprises/docs](https://github.com/hronecviktor/freeq)

Zero-setup end-to-end encrypted message queue for free in 1 line of python

---

## TL;DR;

No need to set up a server, a DB, redis, dedicated queue, hosted pub/sub and worrying about free tier limits, or anything.
`pip install freeq` and go

#### Quickstart for server:
```shell
docker run -d -p 8000:8000 hronecviktor:freeq-server
```
Or build the docker container yourself:
```shell
git clone https://github.com/hronecviktor/freeq-server.git
cd freeq-server
docker build -t freeq-server .
docker run -d -p 8000:8000 freeq-server
```
Configuration env vars with defaults:
```shell
FREEQ_REDIS_BLOCKING_TIMEOUT=60 # wait 60 seconds for a message to arrive before returning empty on blocking calls
FREEQ_REDIS_EXPIRY=172800 # two days in seconds till messages expire
FREEQ_REDIS_MAX_QLEN=2048 # max messages per queue
FREEQ_REDIS_URL=redis://localhost:6379/0 # redis connection string
```