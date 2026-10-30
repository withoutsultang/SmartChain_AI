# SmartChain 핵심 업무 흐름 실행 검증

검증일: 2026-10-30. 실제 서비스와 외부 AI를 연결해 증빙 교체·재분석·재제출까지 검증했습니다.

## 확인 결과

|범위|결과|근거|
|---|---|---|
|백엔드 전체|495개 중 494개 통과·1개 건너뜀, 실패 0개, clean build 성공|[집계](verification/backend-test-summary.json) · [실행](https://github.com/withoutsultang/SmartChain_Backend/actions/runs/41058396126)|
|PostgreSQL HTTP|권한 42개 + 업무 순환·장애 복구 9개, 총 51개 통과|[실행](https://github.com/withoutsultang/SmartChain_Backend/actions/runs/41057940415)|
|프론트|회귀 시험 9개와 프로덕션 빌드 통과|[실행](https://github.com/withoutsultang/SmartChain_Frontend/actions/runs/41057900216)|
|AI|응답 계약·OCR 복구·필수 슬롯 계약 시험 5개 통과|[실행](https://github.com/withoutsultang/SmartChain_AI/actions/runs/41057819667)|
|실제 연동|OpenAI 두 모델·Clova OCR 및 전체 업무 순환, 17개 검사 통과|[최종 실행](https://github.com/withoutsultang/SmartChain_AI/actions/runs/41059678771) · [검증 JSON](verification/verification.json)|
|시연|실제 화면 10개·22초 GIF|[시연](https://github.com/withoutsultang/SmartChain_Frontend/tree/develop/docs/demo)|

## 실제 재제출 순환

기안 생성 → 합성 PDF 9개 업로드 → Preview → AI 분석 → 회사 결재 → 원청 심사 → 보완 요청 → 윤리강령 증빙 교체 → 재분석 → 재결재·재심사 → 최종 승인 순서로 실행했습니다.

첫 분석은 `NEED_CLARIFY / MEDIUM`과 윤리강령의 `E8_SECTION_MISSING`을 반환했습니다. 기안자가 파일 4를 삭제하고 필수 조항을 포함한 파일 10을 업로드했습니다. 재분석은 새 파일을 참조하는 결과 2를 저장했고, 윤리강령 보완 사유가 해소됐습니다. 최종 결과는 `PASS / LOW`입니다. 기존 결과 1도 이력으로 유지했습니다. 같은 Approval·Review ID를 재사용해 마지막 기안 상태 `COMPLETED`를 확인했습니다.

[첫 분석](verification/analysis-result.json) · [재분석](verification/analysis-result-revised.json) · [업무 이력](verification/workflow-history.json)

두 분석 파이프라인의 모델 호출 21회가 모두 성공했습니다. 모델별 성공 여부를 관측해 API 오류로 기본 문구를 반환한 경우를 성공으로 세지 않았습니다. 사전 인증 확인의 모델 호출 2회는 이 21회와 별도입니다. [사용량 기록](verification/ai-usage.jsonl)

## 실행 방법과 근거의 범위

GitHub Actions의 임시 호스트에서 PostgreSQL 16, Java 17/Spring Boot, Python 3.11/AI Run API, Node.js 22/Vite, Chromium을 localhost로 연결했습니다. 사용자 PC나 Azure에 배포한 실행은 아닙니다. 기안 생성은 브라우저 폼으로 수행했습니다. 업로드·분석·후속 상태 변경은 인증된 실제 HTTP API로 실행하고 DB 상태와 실제 프론트 화면을 확인했습니다.

모든 문서는 합성 시험 자료입니다. 위 판정 변화는 해당 자료의 보완·재처리 증거이며, 실제 기업 성과나 모델 정확도 수치가 아닙니다. Clova OCR도 실제 호출했습니다. 로그인 실패 5회 각각의 커밋과 계정 잠금도 이 실행에서 확인했습니다. 임시 DB 캠페인 날짜만 실행일에 맞췄습니다.

시간 초과·HTTP 503·동시 중복 제출·만료된 작업의 늦은 응답·Preview 실패는 별도의 PostgreSQL HTTP 시험에서 외부 응답을 제어해 검증했습니다. AI의 OCR 오류 후 재처리는 실제 PDF 추출 경로에서 OCR 응답을 제어해 시험했습니다. 장애 주입 시험에는 유료 API 호출이 없습니다. [복구 설계·9개 시험 상세](https://github.com/withoutsultang/SmartChain_Backend/blob/dev/docs/workflow-recovery-verification.md)

ESG 필수 슬롯은 [기준 JSON](../contracts/esg-required-slots.json)의 9개로 정렬했습니다. 실제 AI 엔진·백엔드 공통 설정·시험 설정을 두 저장소의 CI에서 대조합니다. YOLO 인원 감지·챗봇/RAG·외부 기사 리스크는 이 실행의 범위가 아닙니다.

## 검증 소스

- [Backend ce785b12](https://github.com/withoutsultang/SmartChain_Backend/commit/ce785b12ec22bcc0b49f98c26f3b778c87caff3d)
- [Frontend b6c76c35](https://github.com/withoutsultang/SmartChain_Frontend/commit/b6c76c350250f51b928fe0d9df33d7f5608e594c)
- [AI a5890392](https://github.com/withoutsultang/SmartChain_AI/commit/a58903922d9198f9bf5888dd852ca2022bd4e798)

이번 개선은 개인 포트폴리오 재검증 시점의 보강입니다. 당시 개인 기여는 각 README의 원본 PR로 구분했습니다. 팀 원본 저장소와 마스터 포트폴리오는 수정하지 않았습니다. 실제 연동은 [검증 스크립트](../scripts/portfolio/README.md)와 `Live portfolio integration` 수동 실행으로 재현합니다. Secrets 원문을 코드·결과 파일에 저장하지 않습니다.
