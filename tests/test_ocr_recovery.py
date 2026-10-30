"""Exercise real scanned-PDF extraction and FastAPI responses with a controlled OCR fault."""
import sys
from pathlib import Path
import json
from datetime import date
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import httpx
import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'apps/ai_run_api'))
from app.main import app
from app.engines.esg.slots import get_required_slot_names

class OcrRecoveryTest(unittest.IsolatedAsyncioTestCase):
    async def test_ocr_failure_is_explicit_and_retry_uses_fresh_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'ethics_code.pdf'
            doc = fitz.open(); doc.new_page(); doc.save(path); doc.close()
            payload = {'package_id':'ocr-retry','domain':'esg','period_start':'2026-01-01','period_end':'2026-12-31',
                       'files':[{'file_id':'1','storage_uri':str(path),'file_name':path.name}],
                       'slot_hint':[{'file_id':'1','slot_name':'esg.ethics.code'}]}
            llm = AsyncMock(return_value=json.dumps({'why':'synthetic validation','dates':[],'has_signature':False}))
            ocr = AsyncMock(side_effect=[httpx.ReadTimeout('controlled OCR timeout'), 'Ethics code 2026-10-30'])
            with patch('app.extractors.pdf_text.run_ocr', ocr), patch('app.pipeline.submit.ask_llm', llm):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    first = await client.post('/run/submit', json=payload)
                    second = await client.post('/run/submit', json=payload)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            slot = lambda r: next(s for s in r.json()['slot_results'] if s['slot_name']=='esg.ethics.code')
            self.assertIn('OCR_FAILED', slot(first)['reasons'])
            self.assertEqual(slot(first)['verdict'], 'NEED_FIX')
            self.assertNotIn('OCR_FAILED', slot(second)['reasons'])
            self.assertEqual(ocr.await_count, 2)

    async def test_required_slots_match_canonical_contract(self):
        expected=json.loads((ROOT/'contracts/esg-required-slots.json').read_text())['required_slots']
        self.assertEqual(sorted(get_required_slot_names()), expected)
