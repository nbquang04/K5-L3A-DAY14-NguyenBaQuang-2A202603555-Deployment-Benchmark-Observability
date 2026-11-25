from datetime import datetime, timezone
from fastapi import HTTPException
from app.config import settings
from app.redis_client import r

# Reserve estimated usage before work, atomically against daily AND monthly caps.
RESERVE = """
for i = 1, 2 do
    if tonumber(redis.call('GET', KEYS[i]) or '0') + tonumber(ARGV[1]) > tonumber(ARGV[i+1]) then
        return 0
    end
end
for i = 1, 2 do
    redis.call('INCRBYFLOAT', KEYS[i], ARGV[1])
    redis.call('EXPIRE', KEYS[i], tonumber(ARGV[i+3]))
end
return 1
"""

def budget_keys() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return f'budget:day:{now:%Y-%m-%d}', f'budget:month:{now:%Y-%m}'

def token_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * settings.price_input_per_1k + output_tokens * settings.price_output_per_1k) / 1000

def check_budget(estimated_cost: float = 0) -> tuple[str, str]:
    keys = budget_keys()
    if not r.eval(RESERVE, 2, *keys, estimated_cost, settings.daily_budget_usd, settings.monthly_budget_usd, 2 * 86400, 62 * 86400):
        raise HTTPException(status_code=402, detail='LLM budget exceeded')
    return keys

def record_cost(input_tokens: int, output_tokens: int, *, reserved: float = 0, keys: tuple[str, str] | None = None) -> float:
    cost = token_cost(input_tokens, output_tokens)
    with r.pipeline(transaction=True) as pipe:
        for key, ttl in zip(keys or budget_keys(), (2 * 86400, 62 * 86400)):
            pipe.incrbyfloat(key, cost - reserved)
            pipe.expire(key, ttl)
        pipe.execute()
    return cost
