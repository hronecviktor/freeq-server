import os
import time

from fastapi import FastAPI, Path, Query, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis as AsyncRedis
from typing_extensions import Annotated


REDIS_BLOCKING_TIMEOUT = int(os.getenv("REDIS_BLOCKING_TIMEOUT", 60))
REDIS_EXPIRY = int(os.getenv("REDIS_EXPIRY", 60 * 60 * 24 * 2))
REDIS_MAX_QLEN = int(os.getenv("REDIS_MAX_QLEN", 2048))
REDIS_PWD = os.getenv("REDIS_PWD", None)


app = FastAPI()
r = AsyncRedis(
    password=REDIS_PWD,
)


class Event(BaseModel):
    data: Annotated[
        str,
        Query(
            title="Encrypted and base64-encoded event data",
            min_length=1,
            max_length=1024,
        ),
    ]


class Message(BaseModel):
    success: bool
    message: str
    event: Event | None = None
    tstamp: Annotated[
        str, Query(title="Event unix timestamp in microseconds")
    ] | None = None


Queue = Annotated[str, Path(title="Queue name", min_length=8, max_length=256)]
Key = Annotated[str, Path(title="Queue access key", min_length=16, max_length=256)]


@app.get("/")
async def hi():
    return (
        "Priority one — Ensure return of organism for analysis. All other considerations secondary. Crew expendable.",
        200,
    )


@app.get(
    "/{queue}/{key}",
    status_code=status.HTTP_200_OK,
    response_model=Message | None,
    response_model_exclude_unset=True,
    responses={
        204: {"description": "Queue is empty", "content": None},
    },
)
async def get_event(
    response: Response,
    queue: Queue,
    key: Key,
    ack: bool = True,
    block: bool = False,
):
    redis_key = f"{queue}-{key}"

    if block:
        data = await r.bzpopmin(redis_key, timeout=REDIS_BLOCKING_TIMEOUT)
        if data is not None:
            _, payload, tstamp = data
        else:
            # Timeout - queue is empty, poll again
            response.status_code = status.HTTP_204_NO_CONTENT
            return
        if not ack:
            # Redis has no blocking zrangebyscore, so we need to re-add the event
            await r.zadd(redis_key, {payload: tstamp})
    else:
        if ack:
            try:
                payload, tstamp = (await r.zpopmin(redis_key))[0]
            except (IndexError, ValueError):
                payload = None
        else:
            try:
                payload, tstamp = (await r.zrange(redis_key, 0, 0, withscores=True))[0]
            except (IndexError, ValueError):
                payload = None
        if not payload:
            # Queue is empty
            response.status_code = status.HTTP_204_NO_CONTENT
            return

    payload = payload.decode("utf-8").split("-", 1)[1]
    return Message(
        success=True,
        message="",
        event=Event(data=payload),
        tstamp=str(tstamp),
    )


@app.post(
    "/{queue}/{key}/{tstamp}",
    status_code=status.HTTP_200_OK,
    response_model=Message,
    response_model_exclude_unset=True,
    responses={
        404: {
            "description": "Event not found",
            "model": Message,
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Event 1701354548196410 not found in queue '123'",
                    }
                }
            },
        },
    },
)
async def ack_event(
    response: Response,
    queue: Queue,
    key: Key,
    tstamp: str,
):
    redis_key = f"{queue}-{key}"
    num_acked = await r.zremrangebyscore(redis_key, tstamp, tstamp)
    if not num_acked:
        response.status_code = status.HTTP_404_NOT_FOUND
        return Message(
            success=False, message=f"Event {tstamp} not found in queue '{queue}'"
        )
    return Message(success=True, message=f"Event {tstamp} acked in queue '{queue}'")


@app.delete(
    "/{queue}/{key}",
    status_code=status.HTTP_200_OK,
    response_model=Message,
    response_model_exclude_unset=True,
)
async def clear_queue(
    queue: Queue,
    key: Key,
):
    redis_key = f"{queue}-{key}"
    await r.delete(redis_key)
    return Message(success=True, message=f"Cleared queue '{queue}'")


@app.post(
    "/{queue}/{key}",
    status_code=status.HTTP_201_CREATED,
    response_model=Message,
    response_model_exclude_unset=True,
    responses={
        409: {
            "description": "Queue is full",
            "model": Message,
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": 'Queue "123" is full. Consume existing events or clear the queue',
                    }
                }
            },
        }
    },
)
async def post_event(
    response: Response,
    queue: Queue,
    key: Key,
    event: Event,
):
    redis_key = f"{queue}-{key}"
    if await r.zcard(redis_key) > REDIS_MAX_QLEN:
        response.status_code = status.HTTP_409_CONFLICT
        return Message(
            success=False,
            message=f'Queue "{queue}" is full. Consume existing events or clear the queue',
        )

    tstamp = str(int(round(time.time(), 6) * 1000000))
    payload = f"{tstamp}-{event.data}"

    await r.zadd(redis_key, {payload: tstamp})
    await r.expire(redis_key, REDIS_EXPIRY)
    return Message(
        success=True,
        message=f"Added event {tstamp} to queue '{queue}'",
        tstamp=str(tstamp),
    )
