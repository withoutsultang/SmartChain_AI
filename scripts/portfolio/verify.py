"""Real HTTP/DB/API workflow and actual browser captures. Synthetic documents only."""
import asyncio
from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import fitz
import httpx
from openai import AsyncOpenAI
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright, expect
import psycopg

OUT = Path(os.environ.get('PORTFOLIO_RESULTS', '/tmp/portfolio-results'))
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8080/api/v1'
WEB = 'http://127.0.0.1:5173'
report = {'checks': [], 'sources': {}, 'environment': 'isolated localhost services on GitHub Actions', 'synthetic_data': True}
for name in ('backend', 'frontend', 'ai'):
    report['sources'][name] = subprocess.check_output(['git', '-C', name, 'rev-parse', 'HEAD'], text=True).strip()

def check(name, detail=None):
    report['checks'].append({'name': name, 'passed': True, 'detail': detail})
    print('PASS:', name, flush=True)

def save():
    (OUT / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))

api = httpx.Client(base_url=BASE, timeout=200, trust_env=False)
db = psycopg.connect('postgresql://esg:portfolio-local-only@localhost:5432/smartchain', autocommit=True)

def req(method, path, token=None, **kwargs):
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    r = api.request(method, path, headers=headers, **kwargs)
    if r.status_code >= 400:
        try:
            code = r.json().get('code')
        except Exception:
            code = None
        raise AssertionError(f'{method} {path}: HTTP {r.status_code}, code={code}')
    return r.json()['data']

def login(email):
    return req('POST', '/auth/login', json={'email': email, 'password': 'Test1234!'})['accessToken']

async def external_preflight(image):
    # Tiny real calls, no SDK retries, no secrets/URLs in exception output.
    sdk = AsyncOpenAI(api_key=os.environ['OPENAI_API_KEY'], max_retries=0, timeout=45)
    for model in ('gpt-4o-mini', 'gpt-5.1'):
        try:
            result = await sdk.chat.completions.create(model=model, temperature=0, max_completion_tokens=64,
                messages=[{'role': 'user', 'content': 'Reply with exactly OK.'}])
            assert result.choices[0].message.content
            check('Live OpenAI ' + model, {'usage': result.usage.model_dump()})
        except Exception as exc:
            report['checks'].append({'name': 'Live OpenAI ' + model, 'passed': False,
                'error_type': type(exc).__name__, 'status': getattr(exc, 'status_code', None), 'provider_code': getattr(exc, 'code', None)})
            print('FAIL: Live OpenAI', model, type(exc).__name__, getattr(exc, 'status_code', None), getattr(exc, 'code', None), flush=True)
    from app.extractors.ocr.clova_client import run_ocr
    try:
        text = await run_ocr(image, 'png')
        assert 'SMARTCHAIN' in text.upper(), 'Expected synthetic test marker absent'
        check('Live Clova OCR', {'recognized_test_marker': True})
    except Exception as exc:
        report['checks'].append({'name': 'Live Clova OCR', 'passed': False, 'error_type': type(exc).__name__})
        print('FAIL: Live Clova OCR', type(exc).__name__, flush=True)
    await sdk.close()


def analyze_attempt(diagnostic_id, token, hints):
    accepted = req('POST', f'/ai/run/diagnostics/{diagnostic_id}/submit', token, json={'slotHints':hints})
    deadline = time.monotonic()+240
    while time.monotonic()<deadline:
        state = req('GET', f'/ai/run/diagnostics/{diagnostic_id}/status', token)
        assert state['requestId']==accepted['requestId'], 'Accepted analysis attempt was replaced'
        assert state['status']!='FAILED', 'AI attempt failed: '+str(state.get('errorCode'))
        if state['status']=='SUCCEEDED':
            result=req('GET',f'/ai/run/diagnostics/{diagnostic_id}/result', token)
            assert result['id']==state['resultId'], 'Historical result was mistaken for current analysis'
            return result
        time.sleep(1)
    raise AssertionError('AI attempt did not reach a terminal state')


def screenshot(page, name, title=None):
    page.wait_for_timeout(1100)
    if title:
        expect(page.get_by_text(title, exact=False).first).to_be_visible(timeout=15000)
    page.screenshot(path=str(OUT / (name + '.png')), full_page=True, animations='disabled')
    # Fixed viewport frames for a short, readable GIF; no synthetic UI overlays.
    page.screenshot(path=str(OUT / (name + '-frame.png')), animations='disabled')


def browser_login(browser, email):
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='ko-KR')
    page = context.new_page()
    page.goto(WEB + '/login')
    page.get_by_placeholder('이메일을 입력해주세요.').fill(email)
    page.get_by_placeholder('비밀번호를 입력해주세요.').fill('Test1234!')
    page.get_by_role('button', name='로그인', exact=True).click()
    try:
        page.wait_for_url('**/dashboard', timeout=20000)
    except Exception:
        page.screenshot(path=str(OUT/'login-failure.png'), full_page=True)
        raise
    return context, page

try:
    # Each HTTP request has its own service transaction; each DB read is a fresh SELECT.
    locked_email = 'newbie@dongkuk.com'
    for attempt in range(1, 6):
        r = api.post('/auth/login', json={'email': locked_email, 'password': 'wrong'})
        assert r.status_code == (403 if attempt == 5 else 401), (attempt, r.status_code)
        row = db.execute('SELECT failed_login_attempts, locked_until FROM "user" WHERE email=%s', (locked_email,)).fetchone()
        assert row[0] == attempt, (attempt, row[0])
    assert row[1] is not None
    r = api.post('/auth/login', json={'email': locked_email, 'password': 'Test1234!'})
    assert r.status_code == 403
    assert db.execute('SELECT failed_login_attempts FROM "user" WHERE email=%s', (locked_email,)).fetchone()[0] == 5
    check('PostgreSQL: five failed logins persist across HTTP transactions and lock rejects correct password')

    # Refresh dates only inside this disposable validation database.
    db.execute('UPDATE campaign SET period_end_date=CURRENT_DATE+30, deadline=CURRENT_DATE+14 WHERE is_active=true')
    drafter = login('drafter1@posco.com')
    approver = login('approver@posco.com')
    reviewer = login('reviewer.esg@hdhhi.co.kr')
    campaign_id = db.execute("SELECT campaign_id FROM campaign c JOIN domain d USING(domain_id) WHERE d.code='ESG' AND c.is_active=true ORDER BY campaign_id LIMIT 1").fetchone()[0]

    image = Image.new('RGB', (1400, 900), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
    lines = ['SMARTCHAIN TEST DOCUMENT', 'Synthetic portfolio validation - not an actual company record.',
             'Code of Ethics', 'Date: ' + date.today().isoformat(), 'Anti-bribery and fair trade policy.',
             'All employees receive annual ethics training.', 'Prepared by: Demo User', 'Signature: Demo User']
    for i, line in enumerate(lines):
        draw.text((60, 60 + i*85), line, fill='black', font=font)
    buf = io.BytesIO(); image.save(buf, format='PNG'); image_data = buf.getvalue()
    asyncio.run(external_preflight(image_data))
    save()
    if any(not x['passed'] for x in report['checks']):
        raise RuntimeError('Live credential/model/OCR preflight failed; no paid analysis pipeline attempted')

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context, page = browser_login(browser, 'drafter1@posco.com')
        page.goto(WEB + '/diagnostics/new?domainCode=ESG')
        page.get_by_placeholder('기안 제목을 입력하세요').fill('공급망 ESG 증빙 검증 · 포트폴리오 시연')
        page.locator('select[name="campaignId"]').select_option(str(campaign_id))
        expect(page.locator('input[name="periodEndDate"]')).not_to_have_value('')
        screenshot(page, '01-create', '새 기안 생성')
        with page.expect_response(lambda r: '/api/v1/diagnostics' in r.url and r.request.method=='POST') as created:
            page.get_by_role('button', name='기안 생성', exact=True).click()
        assert created.value.status == 201, created.value.status
        diagnostic_id = created.value.json()['data']['diagnosticId']
        check('Browser creates a real persisted ESG diagnostic')
        assert db.execute('SELECT status FROM diagnostic WHERE diagnostic_id=%s', (diagnostic_id,)).fetchone()[0] == 'WRITING'

        # All nine currently required AI ESG slots. Real local files and extraction.
        docs = []
        for filename, slot, label, scanned in [
            ('electricity_usage.pdf','esg.energy.electricity.usage','Electricity usage kWh 2026 monthly: 1000',False),
            ('gas_usage.pdf','esg.energy.gas.usage','Gas usage cubic metres 2026 monthly: 100',False),
            ('msds.pdf','esg.hazmat.msds','Material Safety Data Sheet. Material: water. CAS 7732-18-5. Low hazard.',False),
            ('ethics_code.pdf','esg.ethics.code','Code of Ethics',True),
            ('water_usage.pdf','esg.energy.water.usage','Water usage cubic metres 2026 monthly: 50',False),
            ('chemical_inventory.pdf','esg.hazmat.inventory','Chemical inventory. Material water CAS 7732-18-5. Quantity 100 litres.',False),
            ('ethics_distribution_log.pdf','esg.ethics.distribution.log','Ethics distribution log. Demo User received the policy.',False),
            ('ethics_pledge.pdf','esg.ethics.pledge','Ethics pledge. Demo User agrees to anti-bribery rules.',False),
            ('ethics_poster.pdf','esg.ethics.poster.image','Ethics campaign poster. Fair trade and anti-bribery.',False)]:
            doc = fitz.open(); p = doc.new_page(width=700, height=500)
            if scanned:
                p.insert_image(p.rect, stream=image_data)
            else:
                p.insert_textbox(fitz.Rect(40,40,660,460), '\n'.join(['SMARTCHAIN SYNTHETIC TEST',label,'Date: '+date.today().isoformat(),'Prepared by: Demo User','Signature: Demo User','Portfolio integration test only. No actual business evidence.']), fontsize=15)
            data=doc.tobytes(deflate=True, garbage=4); doc.close()
            uploaded=req('POST',f'/diagnostics/{diagnostic_id}/files',drafter,files={'file':(filename,data,'application/pdf')})
            docs.append({'file_id':str(uploaded['fileId']),'slot_name':slot})
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            rows=req('GET',f'/diagnostics/{diagnostic_id}/files',drafter)
            if len(rows)==len(docs) and all(x['parsingStatus']=='SUCCESS' for x in rows): break
            time.sleep(1)
        else: raise AssertionError('File processing did not finish')
        check('Upload nine real PDFs; local storage and async file bookkeeping complete')
        preview=req('POST',f'/ai/run/diagnostics/{diagnostic_id}/preview',drafter,json={'fileIds':[int(x['file_id']) for x in docs]})
        assert preview['package_id'] and not preview['missing_required_slots'], preview['missing_required_slots']
        check('Backend to actual AI preview covers all nine required ESG slots')
        page.goto(WEB+f'/diagnostics/{diagnostic_id}/files')
        screenshot(page,'02-upload')
        before=len((OUT/'ai-usage.jsonl').read_text().splitlines()) if (OUT/'ai-usage.jsonl').exists() else 0
        result=analyze_attempt(diagnostic_id,drafter,docs)
        (OUT/'analysis-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        assert len(result['details']['slot_results']) >= len(docs)
        calls=[json.loads(line) for line in (OUT/'ai-usage.jsonl').read_text().splitlines()][before:]
        assert calls and all(x['success'] for x in calls), 'AI fallback occurred: inspect sanitized usage log'
        assert any(x['model']=='gpt-5.1' for x in calls)
        assert any(x['model']=='gpt-4o-mini' for x in calls)
        check('Real AI submit persists result; both LLM models completed without API fallback', {'verdict':result['verdict'],'riskLevel':result['riskLevel'],'successful_calls':len(calls)})
        page.goto(WEB+f'/diagnostics/{diagnostic_id}')
        screenshot(page,'03-analysis','AI 분석 결과')
        submitted=req('POST',f'/diagnostics/{diagnostic_id}/submit',drafter,json={'submitComment':'증빙과 AI 분석 결과 검토를 요청합니다.'})
        approval_id=submitted['approvalId'];assert submitted['newStatus']=='SUBMITTED'
        check('ESG diagnostic submits to company approver')
        approver_context,approver_page=browser_login(browser,'approver@posco.com')
        approver_page.goto(WEB+f'/approvals/{approval_id}')
        screenshot(approver_page,'04-approval')
        req('PATCH',f'/approvals/{approval_id}',approver,json={'decision':'APPROVED','comment':'증빙 검토 완료. 원청 심사를 요청합니다.'})
        forwarded=req('POST',f'/approvals/{approval_id}/submit-to-reviewer',approver,json={})
        row=db.execute('SELECT review_id FROM review WHERE diagnostic_id=%s',(diagnostic_id,)).fetchone()
        assert row, 'Approval did not create Review'
        review_id=row[0]
        check('Approver approves and forwards; Review persisted automatically')
        reviewer_context,reviewer_page=browser_login(browser,'reviewer.esg@hdhhi.co.kr')
        reviewer_page.goto(WEB+f'/dashboard/esg/review/{review_id}')
        screenshot(reviewer_page,'05-review')
        req('PATCH',f'/reviews/{review_id}',reviewer,json={'decision':'REVISION_REQUIRED','comment':'시연: 월별 사용량 원장과 담당자 서명 증빙을 보완해 주세요.'})
        assert db.execute('SELECT status FROM diagnostic WHERE diagnostic_id=%s',(diagnostic_id,)).fetchone()[0]=='RETURNED'
        check('Reviewer requests revision; PostgreSQL diagnostic status RETURNED')
        page.goto(WEB+f'/diagnostics/{diagnostic_id}')
        screenshot(page,'06-revision','보완')
        # Complete the drafter revision loop instead of the reviewer's direct re-approval path.
        old_ethics_id=next(d['file_id'] for d in docs if d['slot_name']=='esg.ethics.code')
        req('DELETE',f'/files/{old_ethics_id}',drafter)
        revised=fitz.open(); revised_page=revised.new_page()
        revised_text='윤리강령 보완본\n부패 금품 이해충돌 공정 인권 괴롭힘 개인정보 정보보호 사고 보호 징계\nDate: '+date.today().isoformat()+'\nSignature: Demo User\nSynthetic portfolio validation only.'
        revised_page.insert_textbox(fitz.Rect(40,40,550,700),revised_text,fontname='korea',fontsize=14)
        revised_data=revised.tobytes(deflate=True,garbage=4); revised.close()
        uploaded=req('POST',f'/diagnostics/{diagnostic_id}/files',drafter,files={'file':('ethics_code_revised.pdf',revised_data,'application/pdf')})
        revised_file_id=str(uploaded['fileId'])
        assert revised_file_id!=old_ethics_id
        for d in docs:
            if d['slot_name']=='esg.ethics.code': d['file_id']=revised_file_id
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            rows=req('GET',f'/diagnostics/{diagnostic_id}/files',drafter)
            if len(rows)==len(docs) and all(x['parsingStatus']=='SUCCESS' for x in rows):break
            time.sleep(1)
        else: raise AssertionError('Revised file did not become ready')
        assert all(str(x['fileId'])!=old_ethics_id for x in rows)
        preview=req('POST',f'/ai/run/diagnostics/{diagnostic_id}/preview',drafter,json={'fileIds':[int(d['file_id']) for d in docs],'removedFileIds':[old_ethics_id]})
        assert not preview['missing_required_slots']
        assert all(h['file_id']!=old_ethics_id for h in preview['slot_hint'])
        check('Drafter replaces original evidence, preserves nine-slot coverage and removes stale preview hint')
        page.goto(WEB+f'/diagnostics/{diagnostic_id}/files')
        screenshot(page,'07-reupload')
        revised_result=analyze_attempt(diagnostic_id,drafter,docs)
        assert revised_result['id']!=result['id']
        ethics=next(x for x in revised_result['details']['slot_results'] if x['slot_name']=='esg.ethics.code')
        assert revised_file_id in ethics['file_ids'] and old_ethics_id not in ethics['file_ids']
        assert 'E8_SECTION_MISSING' not in ethics['reasons']
        (OUT/'analysis-result-revised.json').write_text(json.dumps(revised_result,ensure_ascii=False,indent=2))
        all_calls=[json.loads(line) for line in (OUT/'ai-usage.jsonl').read_text().splitlines()]
        assert all(c['success'] for c in all_calls), 'Provider failure was replaced by fallback output'
        check('Reanalysis stores a new result linked to revised evidence and clears the ethics section finding')
        page.goto(WEB+f'/diagnostics/{diagnostic_id}')
        screenshot(page,'08-reanalysis','AI 분석 결과')
        resubmitted=req('POST',f'/diagnostics/{diagnostic_id}/submit',drafter,json={'submitComment':'보완 증빙과 재분석 결과를 제출합니다.'})
        assert resubmitted['approvalId']==approval_id
        req('PATCH',f'/approvals/{approval_id}',approver,json={'decision':'APPROVED','comment':'보완 자료 재검토 완료.'})
        forwarded=req('POST',f'/approvals/{approval_id}/submit-to-reviewer',approver,json={})
        assert forwarded['reviewId']==review_id
        assert db.execute('SELECT count(*) FROM approval WHERE diagnostic_id=%s',(diagnostic_id,)).fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM review WHERE diagnostic_id=%s',(diagnostic_id,)).fetchone()[0]==1
        check('Re-submission reuses Approval and Review IDs and returns to original-company review')
        reviewer_page.goto(WEB+f'/dashboard/esg/review/{review_id}')
        screenshot(reviewer_page,'09-resubmitted-review')
        req('PATCH',f'/reviews/{review_id}',reviewer,json={'decision':'APPROVED','comment':'보완 증빙과 새로운 분석 결과 검토 후 최종 승인.'})
        assert db.execute('SELECT status FROM diagnostic WHERE diagnostic_id=%s',(diagnostic_id,)).fetchone()[0]=='COMPLETED'
        assert db.execute('SELECT count(*) FROM ai_analysis_result WHERE diagnostic_id=%s',(diagnostic_id,)).fetchone()[0]==2
        check('Final approval after actual revision and re-submission; two analysis histories, PostgreSQL COMPLETED')
        report['revision']={'original_file_id':old_ethics_id,'revised_file_id':revised_file_id,'initial_result_id':result['id'],'revised_result_id':revised_result['id']}
        page.goto(WEB+f'/diagnostics/{diagnostic_id}')
        screenshot(page,'10-completed')
        history=req('GET',f'/diagnostics/{diagnostic_id}/history',drafter)
        (OUT/'workflow-history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2))
        check('Workflow audit history is queryable')
        report['workflow_ids']={'diagnostic':diagnostic_id,'approval':approval_id,'review':review_id}
        browser.close()
    frames=[]
    for path in sorted(OUT.glob('*-frame.png')):
        frame=Image.open(path).convert('RGB');frame.thumbnail((1080,750));frames.append(frame.copy())
    frames[0].save(OUT/'smartchain-demo.gif',save_all=True,append_images=frames[1:],duration=2200,loop=0,optimize=True)
    check('Actual application screenshots and short workflow GIF captured')
except Exception as exc:
    # Never serialize raw provider exceptions, URLs, auth headers or tokens.
    report['failure']={'type':type(exc).__name__, 'stage':report['checks'][-1]['name'] if report['checks'] else 'startup'}
    print('VALIDATION FAILED:',type(exc).__name__, flush=True)
    if isinstance(exc, (AssertionError, RuntimeError)):
        print(str(exc)[:300], flush=True)
    if 'page' in globals():
        try:
            page.screenshot(path=str(OUT/'failure-screen.png'), full_page=True)
        except Exception:
            pass
    if isinstance(exc, psycopg.Error):
        print('Database SQLSTATE:', exc.sqlstate, exc.diag.message_primary, flush=True)
    save()
    raise SystemExit(1)
finally:
    save();api.close();db.close()
