# 실제 서비스 통합 검증

`Live portfolio integration` 워크플로는 Azure 배포 없이 한 실행 환경의 localhost에서 PostgreSQL 16, Spring Boot, AI Run API, Vite 프론트를 함께 실행합니다.

- 로그인 실패 5회의 HTTP 요청마다 PostgreSQL을 새로 조회해 카운터와 잠금의 커밋을 확인합니다.
- OpenAI의 light/heavy 모델과 Clova OCR에 소량의 실제 요청을 보냅니다.
- 브라우저에서 기안을 생성하고 실제 파일 저장소·AI 분석·결재·원청 심사·보완 요청·증빙 교체·재분석·재결재·재심사·최종 승인 및 이력을 검증합니다.
- 단계별 실제 화면과 GIF, 소스 커밋, 검증 결과 JSON, 내용과 키를 제외한 AI 사용량을 artifact로 보관합니다.

## 준비

AI 개인 저장소의 Actions Secrets에 `OPENAI_API_KEY`, `CLOVA_INVOKE_URL`, `CLOVA_OCR_SECRET`을 등록합니다. OpenAI·Clova 호출에는 해당 계정의 이용 요금이 발생합니다.

일반 회귀 테스트는 `Portfolio checks`에서 실행하며 외부 API를 호출하지 않습니다. 실제 연동은 `Live portfolio integration`의 수동 실행으로 분리합니다.

## 검증 범위

문서는 모두 프로그램으로 생성한 시연용 데이터입니다. 실제 기업의 측정 결과나 모델 정확도·운영 성능을 증명하는 자료가 아닙니다. 임시 DB의 캠페인 날짜만 실행 시점에 맞게 조정하며 운영 데이터와 팀 원본 저장소는 변경하지 않습니다.

화면은 실제 프론트와 실제 백엔드의 응답으로 캡처합니다. 기안 생성은 브라우저에서 실행하고, 파일 업로드와 분석·후속 상태 전이는 실제 HTTP API로 실행한 후 화면을 확인합니다. 보완 요청 뒤 기안자가 원래 증빙을 삭제하고 보완본을 업로드합니다. 새 파일을 참조하는 별도 분석 결과와 보완 사유 해소를 검사하고, 동일 Approval·Review를 재사용한 재결재·재심사와 최종 COMPLETED를 확인합니다.

AI 관측기는 이 검증 실행에만 출력 상한을 적용하고 모델별 성공 여부·토큰 수만 저장합니다. 응답 문장이나 비밀 값은 관측 로그에 남기지 않습니다. AI 호출이 실패해 서비스의 기본 문구로 대체된 경우 실제 연동 성공으로 판정하지 않습니다.

## 장애 복구와 계약 검사

Backend의 `Workflow and AI recovery verification`은 PostgreSQL과 실제 HTTP 요청으로 시간 초과·503·중복 제출·만료 복구·권한 및 재제출을 검사합니다. 외부 HTTP 응답만 제어하며 유료 API를 쓰지 않습니다. AI의 `python -m unittest discover -s tests`는 OCR 오류 후 재처리와 응답 계약을 검사합니다.

`python scripts/verify_slot_contract.py --backend ../backend`는 실제 AI 엔진과 기준 JSON, 백엔드 공통·시험 YAML이 동일한 필수 ESG 9개를 선언하는지 비교합니다. 일반 CI에서도 실행합니다.
