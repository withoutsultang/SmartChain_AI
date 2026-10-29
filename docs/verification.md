# SmartChain 핵심 업무 흐름 실행 검증

검증일: 2026-10-29. 개인 포트폴리오 저장소의 코드를 실제 실행해, AI 응답이 파일·기안·결재·심사 데이터로 연결되는 경로를 확인했습니다.

## 확인 결과

|범위|결과|근거|
|---|---|---|
|백엔드 전체 테스트·빌드|444개 중 443개 통과, 1개 건너뜀, 실패·오류 0개; clean build 성공|[테스트 집계](verification/backend-test-summary.json) · [백엔드 빌드](https://github.com/withoutsultang/SmartChain_Backend/actions/runs/40818713584)|
|로그인 트랜잭션 회귀 시험|H2에서 서비스 트랜잭션 종료 후 실패 횟수·잠금 조회 성공|[회귀 시험](https://github.com/withoutsultang/SmartChain_Backend/blob/d259f900d798cadc210d556b574bfc456f5035d8/src/test/java/com/smartchain/platform/domain/auth/service/LoginFailurePersistenceTest.java)|
|PostgreSQL 인증 검증|실제 HTTP 로그인 실패 5회가 각각 커밋됨; locked_until 저장; 올바른 비밀번호도 잠금 중 거절|[성공 실행](https://github.com/withoutsultang/SmartChain_AI/actions/runs/40825484560)|
|프론트 빌드·회귀 시험|프로덕션 빌드 및 Preview 3개·로그인 보안 정책 3개 통과|[프론트 실행](https://github.com/withoutsultang/SmartChain_Frontend/actions/runs/40824538098)|
|AI 응답 계약|실제 교차검증 결과의 숫자·배열·중첩 JSON 보존 등 3개 통과|[계약 시험](../tests/test_cross_validation_contract.py)|
|외부 AI 인증|gpt-4o-mini·gpt-5.1 실제 응답, Clova OCR의 합성 문서 문자 인식 성공|[검증 JSON](verification/verification.json)|
|핵심 업무 흐름|기안 → 업로드 → Preview → AI Submit → 결재 → 원청 제출·Review 생성 → 보완 요청 → 최종 승인·이력 확인 성공|[상태 이력](verification/workflow-history.json)|
|시연 자료|실제 화면 7개, 7프레임·15.4초 GIF|[시연](https://github.com/withoutsultang/SmartChain_Frontend/tree/develop/docs/demo)|

## 실행 환경과 방법

GitHub Actions의 임시 호스트에서 PostgreSQL 16, Java 17/Spring Boot, Python 3.11/AI Run API, Node.js 22/Vite, Chromium을 localhost로 연결했습니다. Azure 배포 없이 실행했으며 팀 원본 저장소는 수정하지 않았습니다.

기안 생성은 브라우저 폼으로 수행했습니다. 파일 업로드, 분석 요청, 결재와 심사 변경은 인증된 실제 HTTP API로 수행하고, DB 상태와 실제 프론트 화면을 확인했습니다. 임시 데이터베이스의 캠페인 날짜는 실행 시점에 맞게 조정했습니다.

AI Preview가 현재 요구하는 ESG 증빙 9개를 합성 PDF로 생성했습니다. 이 중 윤리강령은 이미지 기반 스캔 PDF로 만들어 OCR 경로를 사용했습니다. 실제 분석 결과는 9개 슬롯의 판정과 `E8_SECTION_MISSING` 보완 사유를 반환했고, `OCR_FAILED` 사유는 없었습니다. 최종 AI 판정은 `NEED_CLARIFY / MEDIUM`으로 저장됐습니다. 이는 합성 시험 자료에 대한 판정이며 실제 기업의 성과 수치나 모델 정확도 측정값이 아닙니다.

분석 파이프라인에서 모델 호출 11회가 모두 성공했습니다. 기본 문구로 대체된 API 실패를 성공으로 세지 않도록 모델별 성공 여부를 별도로 관측했습니다. [분석 결과](verification/analysis-result.json) · [응답 내용·키를 제외한 사용량](verification/ai-usage.jsonl)

보완 요청 뒤 최종 승인은 서비스의 수신자 재승인 경로로 확인했습니다. 협력사가 증빙을 새로 업로드하는 재제출 시나리오, YOLO 인원 감지, 챗봇/RAG와 외부 기사 리스크 서비스는 이 실행의 대상에 포함하지 않았습니다.

## 재검증 중 반영한 개선

- 인증 실패 예외 후에도 실패 횟수와 계정 잠금이 커밋되도록 보완한 로직을 실제 PostgreSQL에서 확인했습니다.
- 개발 환경에서 사이트 키를 비운 경우 로컬 로그인 정책을 사용할 수 있도록 수정하고, 프로덕션에서는 CAPTCHA를 생략하지 않는 회귀 시험을 추가했습니다. CAPTCHA 준비·실행 실패 시 사용자에게 재시도 안내를 표시합니다.
- 임시 실행 설정은 원본의 50MB multipart 한도와 local 프로필을 보존하도록 구성했습니다.
- 실제 API 검증과 Azure 배포는 수동 실행으로 구성했습니다. 일반 회귀 시험은 API를 호출하지 않습니다.

이 개선은 포트폴리오 재검증 시점의 보강입니다. 팀 프로젝트 당시 기여와 구분하며, 당시 개인 기여는 각 저장소 README의 원본 PR에 연결했습니다.

## 실행한 소스

- [Backend d259f900](https://github.com/withoutsultang/SmartChain_Backend/commit/d259f900d798cadc210d556b574bfc456f5035d8)
- [Frontend 7a4997f7](https://github.com/withoutsultang/SmartChain_Frontend/commit/7a4997f7a39130102057300a6962433f16806fb8)
- [AI e51f0586](https://github.com/withoutsultang/SmartChain_AI/commit/e51f0586b3911a5c90e0b05d197d7d0c0d44ab0b)

실제 통합 검증은 [스크립트](../scripts/portfolio/README.md)와 `Live portfolio integration` 수동 실행으로 재현할 수 있습니다. Secrets 원문은 결과 파일·로그·코드에 저장하지 않습니다.
