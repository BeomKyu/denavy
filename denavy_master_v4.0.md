# Denavy 시스템 아키텍처 명세서 v4.0

## 1. 시스템 개요

### 1.1. 목적

Denavy는 코드 리팩토링, 모듈화, 보일러플레이트 생성 등 반복적인 소프트웨어 개발 파이프라인을 LLM 에이전트를 통해 자동화하기 위한 멀티 에이전트 오케스트레이션 시스템이다. 비결정론적(Non-deterministic) AI의 확률적 추론 과정을 결정론적(Deterministic) 소프트웨어 생명주기(SDLC)에 안전하게 통합하고 제어하는 것을 핵심 목표로 한다.

### 1.2. 핵심 컴포넌트

단일 LLM 에이전트 환경에서 발생하는 컨텍스트 유실(Lost in the Middle), 환각(Hallucination), 태업(Laziness) 현상을 체계적으로 통제하기 위해 시스템은 4개의 독립 모듈로 구성된다.

* **Hwatotbul (Context Memory):** 에이전트의 세션 상태와 작업 문맥을 영구적으로 유지하는 외부 상태 저장소. 절차적 기억(Procedural Memory)과 일화적 기억(Episodic Memory)을 파일시스템 기반으로 관리한다.
* **Registry (Metadata Storage):** 다중 프로젝트의 작업 이력, 프롬프트 버전 및 형상 관리 메타데이터를 관리하는 Git 기반 상태 체크포인트 시스템.
* **Byeorim (Compression DSL):** LLM 컨텍스트 윈도우 한계 극복 및 토큰 소모량 최적화를 위해 설계된 고압축 도메인 특화 언어(DSL).
* **Denavy (Orchestrator):** 상기 3개 모듈을 연동하여 파일 시스템 이벤트 및 멀티 에이전트 워크플로우를 제어하는 코어 엔진. 결정론적 스케줄러와 비동기 메시지 버스를 통해 액터(Actor) 기반 에이전트 그룹을 조율한다.

### 1.3. 아키텍처 변경 이력

| 버전 | 핵심 변경 사항 |
|----|---|
| **v2.0** | 파이썬 하드코딩 기반의 정적(Static) 선형 파이프라인. 예외 발생 시 에러 반환 부재로 인한 시스템 교착 상태(Deadlock) 결함 존재. |
| **v3.0** | HITL 기반 이벤트 주도형 비선형 상태 머신 재설계. 에이전트 물리적 격리(Sandboxing) 및 파일 시스템 기반 상태 관리 메커니즘 도입. |
| **v4.0** | 3단계 명세 주도형(Spec-Driven) 파이프라인으로 전면 개편. 비동기적 적대적 리뷰어(Adversarial Reviewer) 결합, Git 기반 FSM 상태 관리, 액터 모델(Actor Model) 기반 다중 프로젝트 확장 아키텍처 도입. 동적 문맥 탐색(Dynamic Context Discovery) 및 문맥 오프로딩(Context Offloading) 적용. |

---

## 2. 핵심 설계 원칙 (Design Principles)

### 2.1. 명세 주도 개발 (Spec-Driven Development)

자연어 요구사항을 코드로 곧바로 변환하려는 시도에서 발생하는 **'의미론적 틈(Semantic Gap)'**을 해소하기 위해, 모든 코드 구현은 사전에 인간이 승인한 구조화된 명세서(spec.md)를 절대적 기반(Ground Truth)으로 삼아 수행된다. 이 방식은 다음의 효과를 보장한다:

* **환각 억제:** RAG 기반 외부 증거 접지(Grounding)를 통해 존재하지 않는 API/라이브러리 발명(외재적 환각)을 사전 차단한다.
* **태업 방지:** 명세서에 명시된 체크리스트를 기준으로 구현 완료 여부를 기계적으로 대조하여, 에이전트가 어려운 엣지 케이스를 생략하는 행위를 원천 차단한다.
* **추론 효율 극대화:** 코드 생성 전 논리적 계획을 먼저 수립하는 '계획 주도 프로그래밍(Planning-Driven Programming)' 방식으로 Pass@1 비율을 비약적으로 향상시킨다.

### 2.2. 제로 트러스트(Zero-Trust) 기반 접근 제어

에이전트에게 프로덕션 코드베이스(`src/`)에 대한 직접적인 쓰기(Write) 권한을 부여하지 않는다. 모든 코드 생성 및 자체 테스트는 격리된 샌드박스 환경 내에서만 실행되며, 프로덕션 반영은 시스템 관리자의 명시적 승인을 요구한다.

### 2.3. Git 기반 유한 상태 기계 (Git-based FSM)

DB에 의존하지 않고 파일시스템과 Git을 결합하여 에이전트의 전체 생명주기 상태를 관리한다. 에이전트의 상태 전이는 엄격히 정의된 FSM 스키마를 따르며, 임의의 상태로 분기할 수 없다. Git 커밋은 원자적 체크포인트로, 오류 발생 시 `git reset --hard`를 통한 즉시 롤백을 보장한다.

### 2.4. 적대적 교차 검증 (Adversarial Review)

단일 모델 프롬프팅으로 인한 확증 편향 방지를 위해 에이전트 역할을 설계(Architect), 구현(Editor), 검증(Reviewer)으로 물리적으로 분리한다. 각 에이전트 간의 작업 컨텍스트 및 시스템 프롬프트 공유를 차단(Information Firewall)하여, 입력 명세서와 출력 산출물만을 대조하는 객관적 교차 검증을 강제한다.

### 2.5. 동적 문맥 탐색 및 오프로딩 (Dynamic Context Discovery & Offloading)

컨텍스트 비대화(Context Bloat)로 인한 추론 성능 저하를 방지한다. 파이프라인 각 단계의 산출물은 프롬프트 내에 누적되지 않고, 로컬 파일시스템에 마크다운/JSON 파일 형태로 즉시 오프로딩된다. 에이전트는 `grep`, `tail_file`, `read_file_range` 등 Unix 철학 기반 도구를 활용하여 필요한 정보만을 동적으로 탐색한다.

### 2.6. 인간 감독 피로도 최소화 (Supervision Fatigue Reduction)

인간 개발자는 기계가 생성한 코드의 매 줄을 검토하는 대신, 명세서 단계에서 아키텍처 방향성을 승인(Steering)하고 최종 PR 병합 시점에서만 개입한다. 이를 통해 '감독 피로(Supervision Fatigue)' 및 '강도의 덫(Intensity Trap)'을 구조적으로 회피한다.

---

## 3. 파이프라인 아키텍처: 비동기적 리뷰어 결합 3단계 구조

### 3.1. 아키텍처 선택 근거

본 시스템은 기존의 5단계 선형 파이프라인(v3.0)을 **3단계 명세 주도형 파이프라인**으로 재편성한다. 이는 다양한 오케스트레이션 아키텍처의 비교 분석 결과에 기반한다.

| 아키텍처 | 장점 | 한계 | 판정 |
|---|---|---|---|
| **1단계 (Monolithic)** | 구조 단순, 도입 용이 | 컨텍스트 윈도우 한계에 의한 심각한 환각 유발. 확장성 제로. | ❌ 부적합 |
| **2단계 (Planner-Executor)** | 전역 목표 유지, 추론 비용 최대 45% 절감 | 자체 피드백 루프 부재. 실행 결과의 신뢰성 검증 불가. | ⚠️ 불충분 |
| **4단계+ (Deep Pipeline)** | 단계별 전문성 극대화 | 토큰 비용 기하급수적 증가. 지연 시간 과다. 실시간 피드백 불가. | ❌ 과잉 |
| **중첩/병렬 (Nested/Parallel)** | 정보 검색/독립 테스트에서 속도 향상 | 코딩은 강한 의존성을 지닌 선형 작업. 병합 시 상태 일관성 유지 비용 막대. 문맥 오염 발생. | ❌ 도메인 부적합 |
| **3단계 + 적대적 리뷰어** | 환각/태업 원천 통제, 감독 피로도 최소화, 추론 효율 극대화 | — | ✅ **채택** |

### 3.2. 3단계 파이프라인 워크플로우

#### Stage 1: 제약조건 도출 및 RAG 접지 (Constraint Extraction & RAG Grounding)

* **Actor:** Architect Agent & User
* **Input:** 사용자의 추상적 요구사항 (Byeorim DSL 기반 명세)
* **Process:**
    1. 사용자 요구사항을 분석하여 기술적 제약조건(기술 스택, API 호환성, 보안 정책)을 추출한다.
    2. RAG(시맨틱 검색/GraphRAG)를 활용하여 최신 API 문서, 사내 코딩 컨벤션, 보안 규정 등 외부 증거로 모델을 접지(Grounding)시킨다.
    3. `AGENTS.md` 등 절차적 기억(Procedural Memory) 파일을 파일시스템에서 읽어 전역 컨텍스트로 설정한다.
* **Output:** 제약조건 문서 (`spec/dna/constraints.md`)

#### Stage 2: 명세 작성 및 인간 승인 (Specification Generation & HITL Gate)

* **Actor:** Architect Agent → **Human Approval Gate** → User
* **Input:** Stage 1에서 추출된 제약조건 문서
* **Process:**
    1. 논리적 구조, 데이터 모델, 상호작용 설계, 테스트 전략이 포함된 아키텍처 청사진을 생성한다.
    2. 산출물은 토큰 소모를 최소화하기 위해 반드시 벼림 문법(Byeorim DSL) 규격을 따르는 명세서(spec/spec.md) 포맷으로 생성하도록 강제한다.
    3. `spec/test/`에 TDD 기반 검증용 테스트 코드를 생성한다.
    4. **파이프라인이 일시 중지된다.** 인간 개발자가 명세서와 테스트 코드의 적합성을 검토하고, 모호한 요구사항을 보정하며, 누락된 비즈니스 로직을 추가하는 '조향(Steering)' 역할을 수행한다.
* **Output:** 승인된 명세서 (`spec/spec.md`), 검증 테스트 (`spec/test/`)
* **State Transition:** 승인 시에만 Stage 3으로 전이. 거부 시 Stage 1로 롤백.

#### Stage 3: 코드 구현 및 적대적 검증 (Implementation & Adversarial Review Loop)

* **Actor:** Editor Agent ↔ Reviewer Agent (비동기 루프)
* **Input:** 승인된 명세서, 테스트 코드
* **Process:**
    1. **Editor Agent**가 `sandbox/src_draft/`에서 명세서의 단위 기능(Atomic Task)별로 코드를 구현한다.
    2. `spec/test/`의 테스트 케이스를 자율적으로 실행. 모든 테스트 통과(Exit Code 0)까지 코드 수정/디버깅 반복.
    3. `spec/.block` 플래그를 통해 Editor가 테스트 코드를 임의 수정하여 검증을 우회하는 행위를 차단.
    4. 테스트 통과한 코드를 인간에게 바로 넘기지 않고, **Reviewer Agent**에게 비동기적으로 전달한다.
    5. **Reviewer Agent**는 비판과 검증에만 특화된 프롬프트를 보유하며, 초기 명세서(`spec/spec.md`)와 제약조건(`spec/dna/`)을 기준으로 아키텍처 원칙 위반, 논리적 결함, 보안 취약점을 정적 분석한다.
    6. **적대적 협업(Adversarial Collaboration) 사이클:** 결함 발견 시 산출물을 Editor에게 반려(Reject). Editor가 수정 후 재제출. 이 루프는 인간 개입 없이 반복된다.
    7. Reviewer 승인 시, 보안/아키텍처 영향도 분석 서술형 리포트를 의무 첨부하여 `.denavy/4_pending/`으로 이관한다.
* **Git 연동:**
    * Editor는 단위 기능 구현 완료 시마다 구조적 커밋 메시지와 함께 `git commit`을 수행한다.
    * Reviewer 또는 자동화 테스트가 심각한 오류 발견 시, `git reset --hard` 또는 `git revert`를 실행하여 이전 안정 커밋으로 즉시 롤백 후 재구현을 시도한다.
* **Output:** Reviewer 승인 완료 코드 + 분석 리포트 → `.denavy/4_pending/`

#### Final Gate: 최종 승인 및 병합 (Human Final Review & Merge)

* **Actor:** User
* **Input:** `.denavy/4_pending/` 대기열의 코드 + Reviewer 리포트
* **Process:**
    1. 사용자가 Reviewer의 분석 리포트를 기반으로 최종 검토한다.
    2. 자동화 편향(Automation Bias) 방지를 위해, 리포트의 보안 취약점/영향도 항목을 확인한다.
* **Merge:** 승인 완료 시 `src/` 디렉토리에 병합. `git push` / PR 생성은 반드시 인간 승인 후에만 실행된다.
* **Reject:** 거부 시 `sandbox/`로 반려. Editor Agent 재호출.

---

## 4. 표준 디렉토리 아키텍처 및 권한 명세

권한 통제, 상태 전이, 메모리 계층을 위해 아래의 디렉토리 구조 및 접근 제어 목록(ACL)을 강제한다.

```text
/ (Project Root)
├── .denavy/                    (시스템 백그라운드 관리 영역)
│   ├── state.md                [ACL: System(RW)] 벼림 DSL로 작성된 FSM 상태 객체 스냅샷 (폴더 이동 없이 파일 내 텍스트만 업데이트)
│   └── reviewer_reports/       [ACL: Reviewer(W), User(R)] 적대적 검증 통과 후 생성된 보안/아키텍처 분석 리포트 보관소
│
├── spec/                       (아키텍처 제약 및 명세 영역)
│   ├── dna/                    [ACL: All(R)]
│   │   ├── constraints.md      도메인 비즈니스 룰 및 전역 기술 스택 제약사항
│   │   └── agents.md           사내 코딩 컨벤션, 리뷰 가이드라인 등 절차적 기억(Procedural Memory)
│   ├── spec.md                 [ACL: Architect(W), Editor(R), Reviewer(R)]
│   │                           인간 승인 완료된 아키텍처 청사진 (Ground Truth)
│   ├── test/                   [ACL: Architect(W), Editor(R)]
│   │                           TDD 기반 필수 단위/통합 테스트 명세
│   └── .block                  [ACL: System]
│                               Editor 에이전트의 spec/ 쓰기 권한 차단 플래그
│
├── sandbox/                    (에이전트 격리 실행 영역)
│   └── src_draft/              [ACL: Editor(RWX)]
│                               Editor 에이전트의 코드 구현 및 자체 테스트용 워크스페이스
│
├── memory/                     (에이전트 메모리 계층)
│   ├── episodic/               [ACL: System(RW)]
│   │                           실행 로그, 테스트 결과, 디버깅 트레이스 (JSON/로그)
│   ├── progress.md             [ACL: System(RW)]
│   │                           전체 프로젝트 진행 상태 파일 (조기 완료 방지)
│   └── feature_list.md         [ACL: System(RW)]
│                               세부 요구사항별 구현/테스트 통과 상태 추적
│
└── src/                        (프로덕션 릴리즈 영역)
    └── [ACL: User(RW)]
                                사용자 승인 프로세스를 통과한 산출물의 최종 병합 목적지
                                (에이전트 직접 접근 불가)
```

---

## 5. 상태 관리 아키텍처 (State Management)

LLM은 세션 간에 어떠한 상태도 자체적으로 기억하지 못하는 완전한 무상태(Stateless) 엔진이다. 따라서 오케스트레이션 로직과 완전히 분리된, 견고한 영속성 기반의 상태 관리 계층이 필수적으로 요구된다. 무거운 외부 데이터베이스(PostgreSQL, Kafka, Vector DB 등) 도입으로 인한 유지보수 오버헤드와 다중 데이터 저장소 동기화 실패(Polyglot Persistence Failure) 위험을 배제하고, **"Git 기반 유한 상태 기계(FSM) + 파일시스템"** 패턴을 채택한다.

### 5.1. 계층 1: 파일시스템 기반 영구 기억 (Filesystem-first Memory)

LLM은 학습 단계에서 GitHub 레포지토리 구조, 로그 파일 포맷, 마크다운 문서 등 개발자 친화적 인터페이스에 고도로 익숙하다. 이를 활용하여 무거운 Vector DB 대신 프로젝트 폴더 내 파일 구조 자체를 메모리 기질(Memory Substrate)로 활용한다.

| 메모리 유형 | 저장 위치 | 용도 |
|---|---|---|
| **절차적 기억 (Procedural)** | `spec/dna/agents.md` | 코딩 컨벤션, 아키텍처 원칙, 리뷰 가이드라인 등 암묵적 지식의 명시적 텍스트화. 세션 시작 시 자동 로딩. |
| **일화적 기억 (Episodic)** | `memory/episodic/*.md` | 이전 작업의 실행 로그, 테스트 결과, 디버깅 트레이스. 컨텍스트 윈도우 한계 시 자동 압축 요약 후 디스크 오프로딩. |
| **의미론적 기억 (Semantic)** | `memory/episodic/*.md` | 도메인 지식, API 사용 패턴 등 축적된 사실적 지식. 파일 I/O 도구를 통한 검색. |
| **진행 상태 (Progress)** | `memory/progress.md`, `memory/feature_list.md` | 전체 프로젝트 중 구현 완료 지점 추적. '단발성 시도' 및 '조기 완료' 오류 방지. |

### 5.2. 계층 2: 유한 상태 기계(FSM) 스키마 기반 상태 전이 제어

에이전트의 상태를 비정형 채팅 로그가 아닌, 엄격히 정의된 스키마 객체(JSON 스키마)로 강제한다. 에이전트는 임의의 상태로 분기할 수 없으며, 아래에 정의된 FSM 노드만을 따라 이동해야 한다. 각 전환 시 상태 객체의 데이터 타입과 필수 필드가 완벽히 일치해야만 다음 노드로 전이된다.

```
                  ┌──────────────────────────────────────────────┐
                  │                                              │
                  ▼                                              │
┌─────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┴──┐
│ BACKLOG │──▶│ SPEC_ANALYZE │──▶│ SPEC_REVIEW  │──▶│ IMPLEMENTING │
│ (대기)   │   │ (명세 분석중) │   │ (HITL 승인   │   │ (코드 구현중) │
└─────────┘   └──────────────┘   │  대기)       │   └──────┬──────┘
                  ▲              └──────┬───────┘          │
                  │                     │ Reject           │
                  └─────────────────────┘                  │
                                                           ▼
                                              ┌──────────────────┐
                                              │   TEST_RUNNING   │
                                              │  (자동 테스트중)  │
                                              └────────┬─────────┘
                                                       │
                                          ┌────────────┴────────────┐
                                          │ Fail                    │ Pass
                                          ▼                         ▼
                                 ┌────────────────┐     ┌──────────────────┐
                                 │   DEBUGGING    │     │ ADVERSARIAL_     │
                                 │   (수정중)     │     │ REVIEW (검증중)  │
                                 └────────┬───────┘     └────────┬─────────┘
                                          │                      │
                                          │            ┌─────────┴─────────┐
                                          │            │ Reject            │ Pass
                                          │            ▼                   ▼
                                          │   ┌────────────────┐  ┌──────────────┐
                                          └──▶│ IMPLEMENTING   │  │ PENDING_     │
                                              │ (재구현)       │  │ APPROVAL     │
                                              └────────────────┘  │ (승인 대기)  │
                                                                  └──────┬───────┘
                                                                         │
                                                                    ┌────┴────┐
                                                                    │ Reject  │ Approve
                                                                    ▼         ▼
                                                             ┌──────────┐ ┌────────┐
                                                             │IMPLEMENT │ │ MERGED │
                                                             │ING(반려) │ │ (완료)  │
                                                             └──────────┘ └────────┘
```

**FSM 상태 객체 스키마 (md):**

```json
[Byeorim v1.0]
@FSM_STATE

task: string_uuid
state: [ BACKLOG | SPEC_ANALYZE | SPEC_REVIEW | IMPLEMENTING | TEST_RUNNING | DEBUGGING | ADVERSARIAL_REVIEW | PENDING_APPROVAL | MERGED ]
spec_hash: string_sha256
git_ref: string_hash
retry: int / max: int
actor: [ USER | ARCHITECT | EDITOR | REVIEWER | SYSTEM ]
time: iso8601
meta:

test_res: path_or_null

review_rep: path_or_null

err_log: path_or_null
```

### 5.3. 계층 3: Git 기반 트랜잭션 및 체크포인트 (Git-based Checkpointing)

Git을 에이전트의 트랜잭션 관리자이자 상태 저장소로 활용하여, 파일시스템만 사용할 경우 발생하는 '다중 에이전트의 동시 쓰기(Concurrent Write) 충돌' 문제를 해결한다.

| 동작 | Git 대응 | 자율성 수준 |
|---|---|---|
| 진행 상태 파악 | `git status`, `git diff`, `git log` | ✅ 에이전트 완전 자율 |
| 단위 기능 구현 완료 | `git add` + `git commit` (로컬 브랜치) | ✅ 에이전트 완전 자율 |
| 심각한 오류 발생 시 롤백 | `git reset --hard` / `git revert` | ✅ 에이전트 완전 자율 |
| 최종 코드 프로덕션 반영 | `git push` / PR 생성 | 🔒 **인간 승인 필수 (HITL)** |

**핵심 원칙:** 읽기(Read)와 로컬 쓰기(Local Write)는 에이전트에게 전적 자율권을 부여하되, 전역 상태를 영구적으로 변경하는 쓰기(Push/Merge)는 반드시 인간의 명시적 승인을 요구한다.

---

## 6. 다중 프로젝트 확장 아키텍처 (Multi-Project Scaling)

### 6.1. 중앙 집중형 오케스트레이터의 한계

기존의 순차적 라우팅 또는 단일 그래프 제어 방식에서 발생하는 다중 프로젝트 병목:

* **블로킹(Blocking):** 특정 에이전트가 디버깅 루프에 빠질 경우 전체 파이프라인 대기 상태.
* **인프라 충돌:** 프로젝트 A의 DB 초기화가 프로젝트 B의 테스트 데이터를 파괴. 포트 충돌, 컨테이너 이름 중복.
* **문맥 오염(Context Pollution):** 다른 프로젝트의 컨텍스트가 현 작업 프롬프트에 누출.

### 6.2. 액터 모델(Actor Model) 기반 해결

각 에이전트를 독립적 연산 단위인 '액터(Actor)'로 취급한다. 프로젝트별 액터 그룹은 완전히 격리된 샌드박스(독립 프로세스, 메모리 공간, 로컬 파일시스템 경로) 위에서 동작한다.

* **통신:** 메모리 공유 없이 오직 비동기 메시지 패싱(Asynchronous Message Passing)을 통해서만 상호작용.
* **이벤트 버스:** 하나의 거대한 오케스트레이터 대신 이벤트를 발행(Publish)/구독(Subscribe)하는 방식으로 결합도를 낮추어 락(Lock) 대기를 제거.
* **격리:** 프로젝트 A의 액터 그룹과 프로젝트 B의 액터 그룹 간 문맥 오염 및 인프라 충돌 원천 차단.

### 6.3. 결정론적 비동기 스케줄링 (Deterministic Async Scheduling)

LLM 기반 오케스트레이터가 에이전트 할당을 매번 추론하는 것은 토큰 낭비와 환각을 유발한다. 스케줄러는 **LLM 토큰을 단 하나도 소모하지 않는 순수 결정론적 코드**로 구현한다.

* **하트비트:** 백그라운드에서 주기적(예: 60초)으로 하트비트를 발생시키며, 이슈 라벨(To Do, Doing, To Review, To Improve)을 스캔하여 작업 큐를 관리한다.
* **동적 할당:** `To Do` 라벨 이슈 생성 시 대기 중인 3단계 파이프라인 액터 그룹을 동적으로 할당(Dispatch).
* **자동 재호출:** `To Improve` 라벨 상태 변경 시 코더 액터를 자동 비동기 재호출.
* **무한 루프 방지:** 순수 결정론적 코드로 구현하여 LLM 환각에 의한 무한 루프를 기계적으로 차단.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                     결정론적 스케줄러 (LLM 토큰 소모 0)                    │
│                    Heartbeat (60s) + Label Scan                         │
├────────────────┬────────────────┬────────────────┬───────────────────────┤
│   Project A    │   Project B    │   Project C    │   ...                 │
│  (Actor Group) │  (Actor Group) │  (Actor Group) │                       │
│  ┌───────────┐ │  ┌───────────┐ │  ┌───────────┐ │                       │
│  │ Architect │ │  │ Architect │ │  │ Architect │ │                       │
│  │ Editor    │ │  │ Editor    │ │  │ Editor    │ │  선형 확장 가능         │
│  │ Reviewer  │ │  │ Reviewer  │ │  │ Reviewer  │ │                       │
│  └───────────┘ │  └───────────┘ │  └───────────┘ │                       │
│  ⬡ Sandbox A   │  ⬡ Sandbox B   │  ⬡ Sandbox C   │                       │
│  (격리 환경)    │  (격리 환경)    │  (격리 환경)    │                       │
└────────────────┴────────────────┴────────────────┴───────────────────────┘
                           │
                    ┌──────┴──────┐
                    │ Event Bus   │
                    │ (Pub/Sub)   │
                    └─────────────┘
```

---

## 7. 아키텍처 제약사항 및 마이그레이션 전략

### 7.1. 현행 운영 제약사항

| 항목 | 설명 |
|---|---|
| **상태 전이 인터페이스** | 통합 GUI 대시보드 부재. 백그라운드 스케줄러가 완성되기 전까지는, 사용자가 IDE 우측 채팅창(Cursor 등)에서 에이전트에게 명시적으로 /approve 또는 /reject 프롬프트를 입력하여 FSM 상태 전이를 트리거해야 하는 대화형 I/O 의존성이 존재함. |
| **샌드박스 의존성 매핑** | 격리된 `sandbox/` 내 코드가 외부 모듈이나 서드파티 라이브러리를 참조하기 위한 초기 경로 매핑 및 의존성 주입 설정 비용이 높음. |
| **Git 기반 FSM 학습 곡선** | FSM 스키마 및 Git 기반 자동 롤백 메커니즘에 대한 초기 이해와 설정 비용이 존재. |
| **다중 프로젝트 인프라** | 액터 모델 및 이벤트 버스 인프라 구축에 초기 아키텍처 설계 비용이 발생. |

### 7.2. 점진적 도입 전략 (Phased Rollout)

초기 설정 오버헤드를 최소화하기 위해 일괄 적용을 지양하고, 아래 단계에 따라 점진적으로 확장한다.

| 단계 | 범위 | 목표 |
|---|---|---|
| **Phase A** | Stage 1~2 (제약조건 도출 + 명세 작성 + HITL 승인) | 명세 기반 워크플로우 검증. 시스템 설정 의존도가 가장 낮은 구간. |
| **Phase B** | Stage 3 (샌드박스 TDD + 적대적 리뷰어 자율 루프) | 에이전트 자율 코딩 및 교차 검증 검증. Git 기반 롤백 도입. |
| **Phase C** | 다중 프로젝트 확장 (액터 모델 + 결정론적 스케줄링) | 완전 비동기 다중 프로젝트 오케스트레이션. 이벤트 버스 구축. |

---

## 부록: 참고 자료

본 v4.0 아키텍처 설계는 아래의 연구 및 기술 자료에 기반한다.

1. Multi-Agent Systems: Architecture, Patterns, and Production Design (Comet.com)
2. How we built our multi-agent research system (Anthropic)
3. Planning-Driven Programming: A Large Language Model Approach (OpenReview)
4. The Human-in-the-Loop is Tired (Pydantic)
5. Effective harnesses for long-running agents (Anthropic)
6. How to write a good spec for AI agents (Addy Osmani)
7. Building a Multi-Agent AI System with the Actor Model (Medium)
8. DevClaw: Multi-project dev/qa pipeline (GitHub)
9. Comparing File Systems and Databases for Effective AI Agent Memory Management (Oracle)
10. Best Practices for Controlling LLM Hallucinations at the Application Level (Parasoft)
11. AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation (Microsoft Research)
12. Safe ways to let your coding agent work autonomously (Eric Ma)
