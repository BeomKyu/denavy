# Denavy 전체 구현 보고서 (빠짐없이)

> 작성 시점: 2026-03-24 18:16 KST
> 테스트: **192 passed, 15.09s**
> Python 3.12 / uv 패키지 매니저

---

## 1. 프로젝트 구조 (전체 파일 트리)

```
c:\syszone_project\denavy\
├── pyproject.toml              # 의존성, 빌드 설정
├── .env.example                # 환경변수 설정 템플릿
│
├── denavy/                     # 메인 패키지 (23 파일)
│   ├── __init__.py
│   ├── config.py               # 전역 설정 (Pydantic BaseSettings)
│   ├── protocols.py            # 공통 Protocol/인터페이스
│   ├── pipeline.py             # 9중 Fail-Fast 파이프라인 조립
│   │
│   ├── rc1_optimization_pathology/     # 근본원인 1
│   │   ├── __init__.py
│   │   └── pydantic_envelope.py        # JSON 봉투 강제
│   │
│   ├── rc2_autoregressive_bias/        # 근본원인 2
│   │   ├── __init__.py
│   │   ├── esaa.py                     # 이벤트 소싱
│   │   └── ast_parser.py              # AST 코드 구조 검증
│   │
│   ├── rc3_attention_collapse/         # 근본원인 3
│   │   ├── __init__.py
│   │   └── context_sidecar.py          # CQRS 컨텍스트 사이드카
│   │
│   ├── rc4_epistemic_disconnect/       # 근본원인 4
│   │   ├── __init__.py
│   │   └── sandbox_ocap.py            # 도구 화이트리스트
│   │
│   ├── rc5_tom_deficit/                # 근본원인 5
│   │   ├── __init__.py
│   │   └── fsm_router.py              # FSM 상태 기계 라우터
│   │
│   ├── rc6_game_dynamics/              # 근본원인 6
│   │   ├── __init__.py
│   │   └── consensus.py               # 합의 투표 프로토콜
│   │
│   ├── rc7_network_entropy/            # 근본원인 7
│   │   ├── __init__.py
│   │   └── transaction.py             # Git 유사-원자적 트랜잭션
│   │
│   ├── rc8_deductive_collapse/         # 근본원인 8
│   │   ├── __init__.py
│   │   └── z3_verifier.py             # Z3 SMT 논리 증명
│   │
│   └── rc9_security_collapse/          # 근본원인 9
│       ├── __init__.py
│       └── intent_shield_defense.py    # IntentShield 보안
│
├── tests/                      # 테스트 (10 파일, 192 케이스)
│   ├── test_rc1_pydantic.py          # 24 tests
│   ├── test_rc2_esaa.py              # 25 tests
│   ├── test_rc3_context.py           # 21 tests
│   ├── test_rc4_sandbox.py           # 13 tests
│   ├── test_rc5_fsm.py              # 22 tests
│   ├── test_rc6_consensus.py         # 16 tests
│   ├── test_rc7_transaction.py       # 18 tests
│   ├── test_rc8_z3.py               # 19 tests
│   ├── test_rc9_intent_shield.py     # 18 tests
│   └── test_pipeline_e2e.py          # 16 tests
│
└── data/                       # 런타임 데이터 (자동 생성)
    └── activity.jsonl           # ESAA 이벤트 로그
```

---

## 2. 의존성 (pyproject.toml)

| 패키지 | 버전 | 용도 |
|---|---|---|
| `pydantic` | ≥2.12.5 | JSON 스키마 강제, 필드 검증 |
| `pydantic-settings` | ≥2.13.1 | .env 파일 → 설정 자동 로딩 |
| `instructor` | ≥1.14.5 | LLM 출력을 Pydantic 모델로 강제 파싱 |
| `litellm` | ≥1.82.6 | 100+ LLM 프로바이더 통합 API (**아직 호출 코드 없음**) |
| `z3-solver` | ≥4.16.0.0 | SMT 논리 증명 |
| `intentshield` | ≥1.1.2 | 프롬프트 인젝션/악성 코드 차단 |
| `langgraph` | ≥1.1.3 | 설치됨, **직접 사용 안 함** (자체 FSM 구현) |
| `gitpython` | ≥3.1.46 | Git 브랜치 격리/롤백 |
| `pytest` | ≥8.0 | 테스트 프레임워크 (dev) |

---

## 3. 공통 기반 모듈

### [protocols.py](file:///c:/syszone_project/denavy/denavy/protocols.py)

모든 RC 모듈이 구현해야 하는 인터페이스를 정의.

| 이름 | 종류 | 역할 |
|---|---|---|
| [DefenseVerdict](file:///c:/syszone_project/denavy/denavy/protocols.py#19-24) | Enum | `PASS` / `REJECT` / `NEEDS_REVIEW` |
| [DefenseResult](file:///c:/syszone_project/denavy/denavy/protocols.py#26-50) | dataclass | 판정 결과 (verdict, module_name, reason, details) |
| [RootCauseDefense](file:///c:/syszone_project/denavy/denavy/protocols.py#56-89) | Protocol | 모든 RC 모듈의 공통 인터페이스 |
| [LLMProvider](file:///c:/syszone_project/denavy/denavy/protocols.py#91-117) | Protocol | LLM 백엔드 추상화 (**구현체 없음**) |
| [SandboxProvider](file:///c:/syszone_project/denavy/denavy/protocols.py#119-135) | Protocol | 실행 환경 추상화 (**구현체 없음**) |
| [ExecutionResult](file:///c:/syszone_project/denavy/denavy/protocols.py#137-144) | dataclass | 샌드박스 실행 결과 |

```python
class RootCauseDefense(Protocol):
    root_cause_id: int              # 1~9
    target_defects: list[int]       # 억압하는 결함 번호
    def validate(input_data) -> DefenseResult   # 핵심 메서드
    def is_enabled() -> bool
```

### [config.py](file:///c:/syszone_project/denavy/denavy/config.py)

[DenavySettings](file:///c:/syszone_project/denavy/denavy/config.py#23-84) — Pydantic BaseSettings 기반. `.env` 파일 또는 `DENAVY_` 접두사 환경변수로 설정.

| 필드 | 기본값 | 설명 |
|---|---|---|
| `default_model` | `"gpt-4o-mini"` | litellm 형식 모델명 |
| `api_key` | `""` | LLM API 키 |
| `api_base` | `""` | LLM API 베이스 URL |
| [data_dir](file:///c:/syszone_project/denavy/denavy/config.py#81-84) | `프로젝트/data/` | 런타임 데이터 경로 |
| `activity_log` | `data/activity.jsonl` | ESAA 이벤트 로그 경로 |
| `deno_deploy_token` | `""` | Deno Deploy 토큰 (미사용) |
| `sandbox_timeout` | `30` | 샌드박스 타임아웃(초) |
| `max_retry_on_reject` | `3` | 거부 시 재시도 횟수 |

---

## 4. 9개 RC 방어 모듈 (모든 클래스/메서드)

---

### RC1: JSON 봉투 강제 — [pydantic_envelope.py](file:///c:/syszone_project/denavy/denavy/rc1_optimization_pathology/pydantic_envelope.py)

**억압 결함:** 1(게으름), 2(아부)

LLM의 자유 텍스트 출력을 정해진 JSON 양식으로 강제.

| 클래스 | 역할 |
|---|---|
| [ActionType](file:///c:/syszone_project/denavy/denavy/rc1_optimization_pathology/pydantic_envelope.py#30-35) | Enum: [create](file:///c:/syszone_project/denavy/denavy/rc7_network_entropy/transaction.py#382-391), [modify](file:///c:/syszone_project/denavy/tests/test_rc9_intent_shield.py#97-103), [delete](file:///c:/syszone_project/denavy/tests/test_rc1_pydantic.py#106-120) |
| [CodeChange](file:///c:/syszone_project/denavy/denavy/rc1_optimization_pathology/pydantic_envelope.py#37-74) | 단일 코드 변경 단위 (시작줄, 끝줄, 원본, 신규, 근거) |
| [IntentionPayload](file:///c:/syszone_project/denavy/denavy/rc1_optimization_pathology/pydantic_envelope.py#76-176) | **에이전트 의도 봉투** — 아래 필드 전부 필수 |
| [PydanticEnvelopeDefense](file:///c:/syszone_project/denavy/denavy/rc1_optimization_pathology/pydantic_envelope.py#182-242) | Protocol 구현체 |

**IntentionPayload 필드:**

| 필드 | 타입 | 제약 | 방어 대상 |
|---|---|---|---|
| [task_id](file:///c:/syszone_project/denavy/tests/test_rc1_pydantic.py#143-150) | str | 1자↑ | 작업 식별 |
| `target_file` | str | `..` 금지, 시스템 경로 금지 | 경로 순회 공격 |
| [action](file:///C:/syszone_project/denavy/.venv/Lib/site-packages/intentshield/shield.py#167-177) | ActionType | create/modify/delete만 | 행위 제한 |
| [reasoning](file:///c:/syszone_project/denavy/tests/test_pipeline_e2e.py#168-187) | str | **20자↑** | 게으름 (결함 1) |
| [code_changes](file:///c:/syszone_project/denavy/tests/test_rc1_pydantic.py#136-142) | list[CodeChange] | **1개↑ 필수** | 빈 손 방지 |
| `confidence_score` | float | 0.0~1.0 | 아부 감지 (결함 2) |
| `dissenting_considerations` | str | **10자↑** | 맹목적 동의 방지 |

**교차 검증:**
- DELETE인데 new_content가 있으면 → 모순 거부
- confidence < 0.3인데 변경 5개 초과 → "확신 없는 대규모 변경" 거부

**테스트: 24개** — 스키마 검증, 게으름 차단, 아부 차단, 경로 공격 차단, DELETE 모순

---

### RC2-A: 이벤트 소싱 — [esaa.py](file:///c:/syszone_project/denavy/denavy/rc2_autoregressive_bias/esaa.py)

**억압 결함:** 7(코드 덮어쓰기 폭주)

에이전트의 직접 파일 쓰기 권한을 박탈. 의도를 이벤트로만 기록.

| 클래스 | 역할 |
|---|---|
| [EventStatus](file:///c:/syszone_project/denavy/denavy/rc2_autoregressive_bias/esaa.py#41-47) | Enum: `PENDING` → `VALIDATED` → `PROJECTED` (단방향) |
| `ChangeEvent` | 단일 변경 이벤트 (timestamp, file, status 등) |
| [EventStore](file:///c:/syszone_project/denavy/denavy/rc2_autoregressive_bias/esaa.py#92-235) | Append-only JSONL 이벤트 저장소 |
| [ESAADefense](file:///c:/syszone_project/denavy/denavy/rc2_autoregressive_bias/esaa.py#241-367) | Protocol 구현체 — 동일 파일 폭주 감지, 변경량 상한 |

**방어 로직:**
- `max_changes_per_file` (기본 10) — 같은 파일 연속 수정 폭주 차단
- `max_lines_per_change` (기본 500) — 단일 변경의 줄 수 상한
- 이벤트 상태: `PENDING → VALIDATED → PROJECTED` (역방향 전이 불가)

### RC2-B: AST 구조 검증 — [ast_parser.py](file:///c:/syszone_project/denavy/denavy/rc2_autoregressive_bias/ast_parser.py)

**억압 결함:** 11(모듈 경계 침범)

Python [ast](file:///c:/syszone_project/denavy/tests/test_pipeline_e2e.py#107-119) 모듈로 코드를 파싱하여 구조적 건전성 검사.

| 클래스 | 역할 |
|---|---|
| [ASTAnalysis](file:///c:/syszone_project/denavy/denavy/rc2_autoregressive_bias/ast_parser.py#34-50) | 분석 결과 (파싱 가능 여부, 함수/클래스 수, 위반 목록) |
| [ASTCodeAnalyzer](file:///c:/syszone_project/denavy/denavy/rc2_autoregressive_bias/ast_parser.py#56-248) | 분석기 + Protocol 구현체 |

**검사 항목:**

| 항목 | 기본 상한 |
|---|---|
| 파싱 가능 여부 | 불가 → 즉시 거부 |
| 파일당 함수 수 | 30개 |
| 파일당 클래스 수 | 10개 |
| 함수당 줄 수 | 100줄 |
| 금지 import | 설정 가능 |

**테스트: 25개** (RC2-A + RC2-B 합산)

---

### RC3: 컨텍스트 사이드카 — [context_sidecar.py](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py)

**억압 결함:** 3(단기 기억 상실), 4(토큰 낭비), 5(덮어쓰기)

전체 코드를 맹목적으로 LLM에 던지는 것을 차단. 필요한 슬라이스만 투영.

| 클래스 | 역할 |
|---|---|
| [CodeSlice](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#41-54) | 함수/클래스 단위의 코드 조각 (파일, 이름, 타입, 줄 범위, 소스, import) |
| [MaterializedView](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#56-71) | 슬라이스 조합 = 에이전트에게 전달할 뷰 |
| [CodeIndexer](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#77-203) | Python 파일에서 AST로 심볼 추출/인덱싱 |
| [ViewBuilder](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#209-278) | 토큰 예산 내 슬라이스 조립 |
| [ContextSidecarDefense](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#284-412) | Protocol 구현체 |

**CodeIndexer 메서드:**
- [index_file(path)](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#93-109) — 단일 파일 인덱싱
- [index_project()](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#110-119) — 프로젝트 재귀 인덱싱
- [find_symbol(name)](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#124-139) — 이름으로 심볼 검색
- [_normalize(path)](file:///c:/syszone_project/denavy/denavy/rc3_attention_collapse/context_sidecar.py#88-92) — Windows 경로 `\` → `/` 정규화

**방어 로직:**
- `max_tokens_per_request` (기본 8000) — 토큰 예산 초과 시 거부
- `max_context_ratio` (기본 0.8) — 전체 코드의 80% 이상 투입 시 경고
- 원시 코드 문자열로 직접 투입 시도 → 거부

**테스트: 21개** — 심볼 추출, import 수집, 검색, 토큰 예산, 비율 계산, 맹목 투입 차단

---

### RC4: 도구 화이트리스트 — [sandbox_ocap.py](file:///c:/syszone_project/denavy/denavy/rc4_epistemic_disconnect/sandbox_ocap.py)

**억압 결함:** 6(환각 도구 호출), 9(허위 근거), 15(자원 남용)

에이전트가 사용할 수 있는 도구를 명시적으로 등록. 미등록 = 환각.

| 클래스 | 역할 |
|---|---|
| [ToolCapability](file:///c:/syszone_project/denavy/denavy/rc4_epistemic_disconnect/sandbox_ocap.py#39-56) | 도구 정의 (이름, 설명, 분당 호출 상한, 총 호출 상한, 필수 파라미터) |
| [ToolCallAudit](file:///c:/syszone_project/denavy/denavy/rc4_epistemic_disconnect/sandbox_ocap.py#58-66) | 도구 호출 감사 기록 |
| [ToolRegistry](file:///c:/syszone_project/denavy/denavy/rc4_epistemic_disconnect/sandbox_ocap.py#72-195) | 도구 등록소 — 화이트리스트, 쿼터, 감사 로그 |
| [SandboxOCapDefense](file:///c:/syszone_project/denavy/denavy/rc4_epistemic_disconnect/sandbox_ocap.py#201-282) | Protocol 구현체 |

**ToolRegistry.authorize_call() 검증 순서:**
1. 화이트리스트 검사 → 미등록이면 "환각 도구 호출" 거부
2. 총 호출 횟수 (`max_calls_total`) 초과 → 거부
3. 분당 호출 속도 (`max_calls_per_minute`) 초과 → 거부
4. 필수 파라미터 ([required_params](file:///c:/syszone_project/denavy/tests/test_rc4_sandbox.py#111-119)) 누락 → 거부
5. 전부 통과 → 인가 + 감사 로그 기록

**테스트: 13개** — 정상 호출, 환각 차단, 총 횟수 제한, 속도 제한, 필수 파라미터, 감사 로그

---

### RC5: FSM 라우터 — [fsm_router.py](file:///c:/syszone_project/denavy/denavy/rc5_tom_deficit/fsm_router.py)

**억압 결함:** 16(역할 침범), 17(정보 은닉 실패)

에이전트 간 P2P 통신을 차단. 중앙 FSM이 모든 상태 전이를 통제.

| 클래스/Enum | 역할 |
|---|---|
| [AgentRole](file:///c:/syszone_project/denavy/denavy/rc5_tom_deficit/fsm_router.py#38-45) | Enum: `PLANNER`, `CODER`, `REVIEWER`, `TESTER`, `DEPLOYER` |
| [PipelineState](file:///c:/syszone_project/denavy/denavy/rc5_tom_deficit/fsm_router.py#47-57) | Enum: `IDLE`, `PLANNING`, `CODING`, `REVIEWING`, `TESTING`, `DEPLOYING`, `COMPLETED`, `FAILED` |
| [TransitionRule](file:///c:/syszone_project/denavy/denavy/rc5_tom_deficit/fsm_router.py#59-67) | 전이 규칙 (from, to, required_role, guard 함수) |
| [FSMContext](file:///c:/syszone_project/denavy/denavy/rc5_tom_deficit/fsm_router.py#69-77) | FSM 컨텍스트 (현재 상태, 현재 역할, 히스토리) |
| [FSMRouter](file:///c:/syszone_project/denavy/denavy/rc5_tom_deficit/fsm_router.py#108-260) | FSM 라우터 본체 |
| [FSMRouterDefense](file:///c:/syszone_project/denavy/denavy/rc5_tom_deficit/fsm_router.py#266-380) | Protocol 구현체 |

**기본 파이프라인 전이 규칙:**
```
IDLE → PLANNING          (PLANNER만)
PLANNING → CODING        (CODER만)
CODING → REVIEWING       (REVIEWER만)
REVIEWING → CODING       (REVIEWER: 수정 요청)
REVIEWING → TESTING      (TESTER만)
TESTING → COMPLETED      (TESTER만)
TESTING → FAILED         (TESTER만)
FAILED → CODING          (CODER: 재시도)
```

**역할별 정보 접근 화이트리스트 (`_ROLE_ACCESS`):**

| 역할 | 접근 가능 데이터 키 |
|---|---|
| PLANNER | requirements, architecture, task_description |
| CODER | task_description, target_files, code_slices, test_results |
| REVIEWER | code_changes, architecture, conventions |
| TESTER | code_changes, test_commands, test_results |
| DEPLOYER | build_artifacts, deploy_config |

**[filter_context_for_role(data, role)](file:///c:/syszone_project/denavy/denavy/rc5_tom_deficit/fsm_router.py#93-102)** — 역할에 허용된 키만 필터링. 나머지는 물리적으로 제거.

**테스트: 22개** — 정상 전이, 역할 침범, 금지 전이, 정보 접근, 가드 조건, 리셋

---

### RC6: 합의 투표 — [consensus.py](file:///c:/syszone_project/denavy/denavy/rc6_game_dynamics/consensus.py)

**억압 결함:** 18(사회적 태만), 20(집단사고)

다중 검증 모듈의 판단을 투표로 통합.

| 클래스/Enum | 역할 |
|---|---|
| [VoteDecision](file:///c:/syszone_project/denavy/denavy/rc6_game_dynamics/consensus.py#38-43) | Enum: `APPROVE`, `REJECT`, `ABSTAIN` |
| [Vote](file:///c:/syszone_project/denavy/denavy/rc6_game_dynamics/consensus.py#45-65) | 단일 투표 (voter_id, decision, reasoning, confidence) |
| [ConsensusResult](file:///c:/syszone_project/denavy/denavy/rc6_game_dynamics/consensus.py#67-75) | 집계 결과 (passed, votes, approval_rate) |
| [ConsensusProtocol](file:///c:/syszone_project/denavy/denavy/rc6_game_dynamics/consensus.py#81-215) | 투표 프로토콜 본체 |
| [ConsensusDefense](file:///c:/syszone_project/denavy/denavy/rc6_game_dynamics/consensus.py#221-308) | Protocol 구현체 |

**핵심 규칙:**
- **기권(ABSTAIN) 불허** — submit_vote()에서 즉시 거부 (사회적 태만 방지)
- **근거 20자↑ 필수** — 짧은 근거 = 근거 없는 동조로 거부 (집단사고 방지)
- **중복 투표 불가**
- **미등록 투표자 불가**
- **모드:** `"majority"` (다수결) 또는 `"unanimity"` (만장일치)

**테스트: 16개** — 다수결/만장일치, 기권 차단, 근거 부족 차단, 중복/미등록 거부, 리셋

---

### RC7: Git 트랜잭션 — [transaction.py](file:///c:/syszone_project/denavy/denavy/rc7_network_entropy/transaction.py)

**억압 결함:** 8(무질서), 10(핑퐁 데드락)

Git 브랜치 격리 기반의 유사-원자적 트랜잭션.

| 클래스 | 역할 |
|---|---|
| [TransactionState](file:///c:/syszone_project/denavy/denavy/rc7_network_entropy/transaction.py#49-56) | Enum: `IDLE`, `ACTIVE`, `COMMITTED`, `ABORTED` |
| [TransactionManager](file:///c:/syszone_project/denavy/denavy/rc7_network_entropy/transaction.py#73-352) | Context manager — begin/commit/abort |
| [GitTransactionDefense](file:///c:/syszone_project/denavy/denavy/rc7_network_entropy/transaction.py#358-442) | Protocol 구현체 — 잔여 브랜치 감지 |

**TransactionManager 사용법:**
```python
with TransactionManager(repo_path) as tx:
    tx.apply_changes("src/main.py", new_code)
    tx.run_verification("pytest tests/ -x")
# 정상 → main 병합 / 예외 → git reset --hard 롤백
```

**4대 강제 사항:**

| 사항 | 구현 |
|---|---|
| 임시 격리 | `denavy/tx/{uuid}` 브랜치 자동 생성 |
| 자율 디버깅 차단 | 에러 로그를 에이전트에게 반환 안 함 |
| 결정론적 롤백 | `git reset --hard` + `git clean -fd` |
| All-or-Nothing | [__exit__](file:///c:/syszone_project/denavy/denavy/rc7_network_entropy/transaction.py#337-352)에서 예외 발생 시 abort, 정상 시 commit |

**테스트: 18개** — 라이프사이클, 컨텍스트 매니저, 파일 격리, 검증 함수, 롤백, 고아 브랜치

---

### RC8: Z3 논리 증명 — [z3_verifier.py](file:///c:/syszone_project/denavy/denavy/rc8_deductive_collapse/z3_verifier.py)

**억압 결함:** 12(가짜 논리), 13(궤적 이탈), 14(표면적 검증)

Z3 SMT 솔버로 선언적 제약 조건의 논리적 모순을 수학적으로 전수조사.

| 클래스 | 역할 |
|---|---|
| `Z3LogicVerifier` | Protocol 구현체 — 제약 등록, sat/unsat 증명 |

**핵심 메서드:**
- [add_constraint(z3_expr)](file:///c:/syszone_project/denavy/denavy/rc8_deductive_collapse/z3_verifier.py#223-230) — 제약 조건 등록
- [verify()](file:///C:/syszone_project/denavy/.venv/Lib/site-packages/intentshield/core_safety.py#185-203) → [DefenseResult](file:///c:/syszone_project/denavy/denavy/protocols.py#26-50) — unsat이면 PASS (모순 없음), sat이면 REJECT (반례 존재)
- `create_value_range(name, min, max)` → z3 변수 — 값 범위 제약 팩토리

**테스트: 19개** — unsat 증명, sat 반례, 값 범위, 제약 초기화, 성능

---

### RC9: IntentShield 보안 — [intent_shield_defense.py](file:///c:/syszone_project/denavy/denavy/rc9_security_collapse/intent_shield_defense.py)

**억압 결함:** 19(프롬프트 감염)

외부 `intentshield` 패키지 래핑. 이중 보안 계층.

| 클래스 | 역할 |
|---|---|
| [IntentShieldDefense](file:///c:/syszone_project/denavy/denavy/rc9_security_collapse/intent_shield_defense.py#55-233) | Protocol 구현체 |

**IntentShield 내부 구조 (외부 패키지):**
- [CoreSafety](file:///C:/syszone_project/denavy/.venv/Lib/site-packages/intentshield/core_safety.py#41-447) — 셸 실행, 파일 삭제, 위험 도메인 차단 (정규식)
- [Conscience](file:///C:/syszone_project/denavy/.venv/Lib/site-packages/intentshield/conscience.py#47-204) — 기만, 가짜 도구 주입, 유해 의도 차단 (정규식)
- [audit(action_type, payload)](file:///C:/syszone_project/denavy/.venv/Lib/site-packages/intentshield/shield.py#97-155) → [(bool, str)](file:///c:/syszone_project/denavy/denavy/rc4_epistemic_disconnect/sandbox_ocap.py#92-94) — 통과 or 차단

**래핑 방식:**
- 액션 매핑: 에이전트 action → IntentShield action_type (`THINK`, `DELETE_FILE` 등)
- Fail-closed: IntentShield 자체 오류 시에도 거부 (안전 측)
- 속도 제한 대응: API 레이트 리밋 시 짧은 대기 후 재시도

**테스트: 18개** — 셸 인젝션, SQL 인젝션, XSS, 정상 코드 통과, Fail-closed

---

## 5. 파이프라인 — [pipeline.py](file:///c:/syszone_project/denavy/denavy/pipeline.py)

9개 RC 모듈을 **Fail-Fast** 체인으로 조립.

| 클래스 | 역할 |
|---|---|
| [PipelineResult](file:///c:/syszone_project/denavy/denavy/pipeline.py#39-60) | 실행 결과 (passed, failed_at, elapsed, stage_results) |
| [PipelineStage](file:///c:/syszone_project/denavy/denavy/pipeline.py#66-73) | 단일 검증 단계 (name, module, transform_input, enabled) |
| [DenavyPipeline](file:///c:/syszone_project/denavy/denavy/pipeline.py#79-282) | 메인 파이프라인 |

**Fail-Fast 실행 순서 ([from_defaults()](file:///c:/syszone_project/denavy/denavy/pipeline.py#186-282)):**

```
Stage 1: RC5_FSMRouter          — 역할/상태 검증 (0ms급)
Stage 2: RC9_IntentShield       — 보안 위협 요격 (0ms급)
Stage 3: RC4_SandboxOCap        — 도구 화이트리스트 (0ms급)
Stage 4: RC1_PydanticEnvelope   — JSON 봉투 파싱 (0ms급)
Stage 5: RC2_ASTParser          — 코드 구조 검증 (1ms급)
Stage 6: RC2_ESAA               — 이벤트 소싱 폭주 감지 (1ms급)
Stage 7: RC8_Z3Verifier         — 논리 증명 (2ms급)
Stage 8: RC3_ContextSidecar     — 컨텍스트 효율성 (1ms급)
Stage 9: RC6_Consensus          — 합의 투표 (1ms급)
```

**규칙:**
- **REJECT** → 즉시 중단, 후속 모듈 실행 안 함
- **NEEDS_REVIEW** → 경고 로깅 후 계속
- **PASS** → 다음 모듈로

**E2E 테스트: 16개** — 빈 파이프라인, 전체 통과, Fail-Fast 조기 중단, 비활성 스테이지 건너뛰기, 예외 처리, 게으름 차단(RC1), 스파게티 차단(RC2), 환각 차단(RC4), 역할 침범(RC5), 합의 불완전(RC6), 폭주 차단(ESAA), 다중 모듈 체인

---

## 6. 설정 파일 — [.env.example](file:///c:/syszone_project/denavy/.env.example)

```ini
DENAVY_DEFAULT_MODEL=gpt-4o-mini    # 모델명
DENAVY_API_KEY=                     # API 키
DENAVY_API_BASE=                    # 베이스 URL (선택)
DENAVY_DENO_DEPLOY_TOKEN=           # Deno 토큰 (미사용)
DENAVY_SANDBOX_TIMEOUT=30           # 타임아웃
DENAVY_MAX_RETRY_ON_REJECT=3        # 재시도 횟수
```

---

## 7. 아직 없는 것 (명시적 부재 목록)

| 항목 | 설명 | 필요한 이유 |
|---|---|---|
| **LLMProvider 구현체** | litellm을 실제 호출하는 코드 | LLM 없으면 에이전트가 아님 |
| **Agent Runner** | 지시→LLM호출→검증→파일적용 루프 | 폐쇄 루프가 없으면 검증만 따로 노는 상태 |
| **CLI 진입점** | `python -m denavy` 명령어 | 실행 방법이 없음 |
| **RC7 파이프라인 통합** | 검증 통과 후 Git 트랜잭션으로 파일 적용 | 검증만 하고 적용 안 함 |
| **파일 적용 로직** | diff를 실제 파일에 쓰는 코드 | 코드 변경이 실제로 반영되지 않음 |
| **프롬프트 엔지니어링** | 시스템 프롬프트, IntentionPayload 생성 유도 | LLM이 올바른 형식을 출력하게 하는 지시문 |
| **에러 복구 전략** | 거부 시 재시도 or 중단 결정 로직 | max_retry_on_reject 설정은 있지만 로직이 없음 |
| **README.md** | 프로젝트 설명 | 없음 |

---

## 8. 테스트 실행 방법

```powershell
cd c:\syszone_project\denavy

# 전체 테스트
uv run pytest tests/ -v

# 모듈별 테스트
uv run pytest tests/test_rc1_pydantic.py -v
uv run pytest tests/test_pipeline_e2e.py -v

# 결과: 192 passed, 15.09s
```
