"""Start the real API; record usage/status only, never prompts or credentials."""
import json
import os
from pathlib import Path
import time
import uvicorn
from app.llm import client

log = Path(os.environ.get('PORTFOLIO_RESULTS', '/tmp/portfolio-results'))
log.mkdir(parents=True, exist_ok=True)
sdk = client._get_client()
original = sdk.chat.completions.create

async def observed(*args, **kwargs):
    started = time.monotonic()
    row = {'model': kwargs.get('model')}
    # Bound this validation run's generated output; production client is unchanged.
    kwargs.setdefault('max_completion_tokens', 1500)
    try:
        response = await original(*args, **kwargs)
        row.update(success=True, usage=response.usage.model_dump() if response.usage else {})
        return response
    except Exception as exc:
        row.update(success=False, error_type=type(exc).__name__, status=getattr(exc, 'status_code', None))
        raise
    finally:
        row['seconds'] = round(time.monotonic() - started, 2)
        with (log / 'ai-usage.jsonl').open('a') as f:
            f.write(json.dumps(row) + '\n')

sdk.chat.completions.create = observed
uvicorn.run('app.main:app', host='127.0.0.1', port=8000, log_level='warning')
