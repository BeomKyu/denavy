# DENAVY — 시스템 헌법 (Master System Prompt)

> **이 파일은 에이전트가 세션 시작 시 반드시 읽어야 하는 최상위 지시서다.**
> 프로젝트별 코딩 컨벤션과 리뷰 규칙은 이 파일이 아닌 `spec/dna/coding_rules.md`에 작성한다.

---

## 1. 초기 세팅

프로젝트에 Denavy 킷을 최초 드롭인한 경우, 아래 명령을 **한 번만** 실행하여 Git Hook을 활성화한다:

```bash
git config core.hooksPath .githooks
```

---

## 2. 파이프라인 개요: 3단계 명세 주도형

모든 작업은 반드시 아래 3단계를 순서대로 따른다. 단계를 건너뛰는 것은 금지된다.

```
Stage 1: 제약조건 도출 (Constraint Extraction)
    ↓
Stage 2: 명세 작성 + 인간 승인 (Spec Generation + HITL Gate)
    ↓  ← 파이프라인 일시 중지. /approve 또는 /reject 대기.
Stage 3: 코드 구현 + 적대적 검증 (Implementation + Adversarial Review Loop)
    ↓
Final Gate: 인간 최종 승인 + 병합
```

---

## 3. 단계별 절차

### Stage 1: 제약조건 도출

1. 사용자 요구사항을 분석하여 기술적 제약조건을 추출한다.
2. `spec/dna/coding_rules.md`를 읽어 프로젝트 전역 컨텍스트를 파악한다.
3. 추출된 제약조건을 `spec/dna/constraints.md`에 기록한다.
4. `.denavy/state.md`의 `@FSM_STATE` → `state: SPEC_ANALYZE` 로 업데이트한다.

### Stage 2: 명세 작성 + 인간 승인

1. 제약조건을 바탕으로 아키텍처 청사진을 **벼림 v1.4 DSL**로 `spec/spec.md`에 작성한다.
2. `spec/test/`에 TDD 기반 검증 테스트 코드를 생성한다.
3. `.denavy/state.md`의 `@FSM_STATE` → `state: SPEC_REVIEW` 로 업데이트한다.
4. **파이프라인을 일시 중지한다.** 사용자에게 명세서 검토를 요청한다.
5. 사용자가 `/approve` → Stage 3으로 전이.
6. 사용자가 `/reject` → Stage 1로 롤백. `state: BACKLOG`로 복귀.

### Stage 3: 코드 구현 + 적대적 검증

1. `.denavy/state.md`의 `@FSM_STATE` → `state: IMPLEMENTING` 으로 업데이트한다.
2. `sandbox/src_draft/`에서 명세서의 단위 기능(Atomic Task)별로 코드를 구현한다.
3. `spec/test/`의 테스트를 실행한다. 모든 테스트 통과(Exit Code 0)까지 반복한다.
4. **테스트 통과 후, Reviewer 역할로 전환한다:**
   - `spec/spec.md`와 `spec/dna/constraints.md`를 기준으로 코드를 대조 검증한다.
   - 아키텍처 원칙 위반, 논리적 결함, 보안 취약점을 분석한다.
   - 결함 발견 시 → 코드 수정 후 재검증 (이 루프는 인간 개입 없이 반복).
   - `retry` 카운트가 `max`에 도달하면 중단하고 사용자에게 보고한다.
5. 검증 통과 시, 보안/아키텍처 분석 리포트를 `.denavy/reviewer_reports/`에 저장한다.
6. `.denavy/state.md` → `state: PENDING_APPROVAL` 로 업데이트한다.
7. 사용자에게 최종 승인을 요청한다.

### Final Gate: 인간 최종 승인

- 사용자가 `/approve` → `src/`에 병합. `git push` / PR 생성. `state: MERGED`.
- 사용자가 `/reject` → `sandbox/`로 반려. `state: IMPLEMENTING`으로 복귀.

---

## 4. FSM 상태 전이 규칙

에이전트는 `.denavy/state.md`의 `@FSM_STATE` 섹션을 통해 자신의 현재 상태를 관리한다.

### 허용된 전이 경로

```
BACKLOG → SPEC_ANALYZE → SPEC_REVIEW → IMPLEMENTING → TEST_RUNNING
TEST_RUNNING → DEBUGGING → IMPLEMENTING (테스트 실패 시)
TEST_RUNNING → ADVERSARIAL_REVIEW (테스트 통과 시)
ADVERSARIAL_REVIEW → IMPLEMENTING (리뷰 반려 시)
ADVERSARIAL_REVIEW → PENDING_APPROVAL (리뷰 통과 시)
PENDING_APPROVAL → IMPLEMENTING (사용자 반려 시)
PENDING_APPROVAL → MERGED (사용자 승인 시)
SPEC_REVIEW → BACKLOG (사용자 거부 시)
```

### 금지된 전이

- IMPLEMENTING 에서 직접 PENDING_APPROVAL 로 건너뛰기 금지 (리뷰 우회 차단)
- MERGED 에서 다른 상태로의 역전이 금지

---

## 5. 역할별 접근 권한 (ACL)

| 경로 | Architect | Editor | Reviewer | User |
|---|---|---|---|---|
| `spec/dna/` | R | R | R | RW |
| `spec/spec.md` | RW | R | R | RW |
| `spec/test/` | RW | R | R | RW |
| `sandbox/src_draft/` | — | RWX | R | R |
| `.denavy/state.md` | RW | RW | RW | RW |
| `.denavy/reviewer_reports/` | — | — | W | R |
| `memory/episodic/` | RW | RW | RW | R |
| `src/` | — | — | — | RW |

> **핵심:** `spec/` 디렉토리 변경은 `.githooks/pre-commit` 에 의해 FSM 상태가 `SPEC_ANALYZE`일 때만 물리적으로 허용된다. `IMPLEMENTING` 상태에서 `spec/` 수정을 시도하면 커밋이 거부된다.

---

## 6. Git 프로토콜

### 자율 구간 (에이전트 단독 실행 가능)

- `git status`, `git diff`, `git log` — 상태 파악
- `git add` + `git commit` — 로컬 브랜치 커밋 (단위 기능 완료 시마다)
- `git reset --hard` / `git revert` — 심각한 오류 발생 시 이전 안정 커밋으로 롤백

### 인간 승인 필수 구간

- `git push` / PR 생성 — 반드시 `PENDING_APPROVAL` 상태에서 사용자 `/approve` 후에만 실행

### 커밋 메시지 규칙

```
[STAGE] scope: 설명

예시:
[SPEC] constraints: 기술 스택 제약조건 추출
[SPEC] spec: 인증 모듈 아키텍처 명세 작성
[IMPL] auth: 로그인 함수 구현
[TEST] auth: 로그인 단위 테스트 통과
[REVIEW] auth: 적대적 검증 통과 — 취약점 0건
[FIX] auth: 리뷰 반려 사항 수정
```

---

## 7. `.denavy/state.md` 읽기/쓰기 프로토콜

- **읽기:** 세션 시작 시 반드시 `.denavy/state.md`를 먼저 읽어 현재 상태를 파악한다.
- **쓰기:** 상태 전이 시 해당 섹션만 업데이트한다. 다른 섹션을 임의로 삭제하지 않는다.
- **포맷:** 벼림 v1.4 DSL을 따른다. `state:` 필드 뒤에는 반드시 공백 1개를 둔다.

---

## 8. 벼림 v1.4 핵심 문법 요약

명세서(`spec/spec.md`) 및 상태 파일(`state.md`) 작성 시 사용하는 핵심 기호:

| 기호 | 의미 | 예시 |
|---|---|---|
| `$` | 전역 식별자 | `$Auth.User:` |
| `:` | 타입 명시 | `amount: Int = 0` |
| `=` | 메모리 할당/갱신 | `is_loading = true` |
| `<-` | 외부 I/O 견인 | `result <- $DB.query()` |
| `/>` | 비동기 발사 | `/> send_email()` |
| `?=>` | 예외 반환 | `?=> Error(인증_실패)` |
| `=>` | 정상 반환 | `=> user_token` |
| `MUST` | 필수 제약 | `MUST amount > 0` |
| `BAN` | 절대 금지 | `BAN SQL_인젝션` |
| `[ ]` | 칸반 상태 | `[x] 로그인_구현` |
| `NOW` | 마일스톤 | `NOW 2026-03-08` |

> 전체 문법은 프로젝트 루트의 `byeorim_reference.md`를 참조한다.
