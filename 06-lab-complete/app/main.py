import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError
from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost, token_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import MOCK_RESPONSES, ask as llm_ask

class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {'ts': datetime.now(timezone.utc).isoformat(), 'level': record.levelname, 'event': record.getMessage()}
        data.update(getattr(record, 'fields', {}))
        if record.exc_info:
            data['exception'] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)

logger = logging.getLogger('production_agent')
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.handlers = [handler]
logger.propagate = False
logger.setLevel(settings.log_level)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('startup', extra={'fields': {'environment': settings.environment}})
    yield  # Uvicorn drains in-flight requests before shutdown cleanup.
    r.close()
    logger.info('shutdown_complete')

app = FastAPI(title='Production AI Agent', lifespan=lifespan)

@app.middleware('http')
async def request_log(request: Request, call_next):
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers['X-Request-ID'] = request_id
        return response
    finally:
        route = request.scope.get('route')
        logger.info('http_request', extra={'fields': {'request_id': request_id, 'method': request.method,
                    'route': route.path if route else 'unmatched', 'status': status,
                    'ms': round((time.perf_counter() - started) * 1000, 2)}})

@app.exception_handler(RedisError)
async def redis_unavailable(request: Request, exc: RedisError):
    logger.error('redis_unavailable')
    return JSONResponse(status_code=503, content={'detail': 'State store unavailable'})

@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.error('internal_error', exc_info=True)
    return JSONResponse(status_code=500, content={'detail': 'Internal server error'})

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=200)

    @field_validator('question')
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Question cannot be blank')
        return value

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/ready')
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail='Redis unavailable')
    return {'status': 'ready'}

@app.post('/ask')
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    # This mock's output set is known: reserve a safe upper bound before calling it.
    input_tokens = max(1, len(body.question) // 4)
    max_output_tokens = max(max(1, len(text) // 4) for texts in MOCK_RESPONSES.values() for text in texts)
    reserved = token_cost(input_tokens, max_output_tokens)
    keys = check_budget(reserved)
    try:
        answer = llm_ask(body.question)
    except Exception:
        record_cost(0, 0, reserved=reserved, keys=keys)
        raise
    output_tokens = max(1, len(answer) // 4)
    cost = record_cost(input_tokens, output_tokens, reserved=reserved, keys=keys)
    logger.info('llm_call', extra={'fields': {'input_tokens': input_tokens, 'output_tokens': output_tokens, 'cost_usd': cost}})
    return {'question': body.question, 'answer': answer,
            'usage': {'input_tokens': input_tokens, 'output_tokens': output_tokens, 'cost_usd': cost}}
