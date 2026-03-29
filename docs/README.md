# Denavy 문서 가이드

> 이 문서에서 시작하면 전체 맥락을 빠르게 복구할 수 있습니다.

---

## 📖 읽는 순서

### 1. 현재 어디까지 왔는가 → `status/`

돌아왔을 때 **여기부터 읽으세요.** 현재 구현 상태, 뭐가 완성됐고 뭐가 빈 채로 남았는지.

| 파일 | 내용 |
|------|------|
| [codebase_analysis.md](status/codebase_analysis.md) | **현재 상태 전체 분석** — 완성도, 갭 분석, 확정 결정 4개, 다음 단계 |

### 2. 왜 이걸 만드는가 → `theory/`

프로젝트의 존재 이유와 해결하려는 문제 정의.

| 순서 | 파일 | 내용 |
|------|------|------|
| ① | [00_prime_directive.md](theory/00_prime_directive.md) | **제0원칙** — "불편함을 제거한다" |
| ② | [01_20_defects.md](theory/01_20_defects.md) | **20대 결함** — LLM의 치명적 결함 20가지 |
| ③ | [02_9_root_causes.md](theory/02_9_root_causes.md) | **9대 근본 원인** — 20개 결함 → 9개 뿌리로 환원 |

### 3. 어떻게 만드는가 → `research/`

아키텍처 설계의 이론적 근거. 두 문서는 **상호보완** 관계:

| 파일 | 초점 | 한 줄 요약 |
|------|------|-----------|
| [open_source_guide.md](research/open_source_guide.md) | **도구 선택** | "9개 근본 원인을 어떤 오픈소스로 억압하는가" |
| [orchestration_patterns.md](research/orchestration_patterns.md) | **배치 설계** | "9개 모듈을 PRPAO 루프의 어디에 거는가" |

**차이점:**
- `open_source_guide` = 개별 무기 스펙 (Z3, IntentShield, Git, Pydantic, Deno…)
- `orchestration_patterns` = 전투 대형 (PRPAO 훅, Self-Consistency, Reflexion, LATS)

### 4. 아키텍처 다이어그램 → `assets/`

| 파일 | 내용 |
|------|------|
| [pipeline.png](assets/pipeline.png) | 9중 방어 파이프라인 전체 흐름 |
| [z3_verifier_flow.png](assets/z3_verifier_flow.png) | RC8: Pydantic → LLM-Sym → Z3 검증 흐름 |
| [prpao_loop.png](assets/prpao_loop.png) | PRPAO 하이브리드 실행 루프 아키텍처 |

---

## 🗂️ 디렉토리 구조

```
docs/
├── README.md                          ← 지금 읽는 문서
│
├── status/                            ← 현재 상태 (어디까지?)
│   └── codebase_analysis.md           현재 구현 상태 + 다음 단계
│
├── theory/                            ← 이론 기반 (왜?)
│   ├── 00_prime_directive.md          제0원칙
│   ├── 01_20_defects.md               20대 결함
│   └── 02_9_root_causes.md            9대 근본 원인
│
├── research/                          ← 리서치 & 설계 (어떻게?)
│   ├── open_source_guide.md           오픈소스 도구 적용 가이드
│   └── orchestration_patterns.md      오케스트레이션 패턴 연구
│
└── assets/                            ← 이미지
    ├── pipeline.png
    ├── z3_verifier_flow.png
    └── prpao_loop.png
```

---

## 🔑 핵심 맥락 3분 복구

**이 프로젝트가 뭐냐:**
LLM 에이전트의 확률론적 무질서(환각, 게으름, 폭주…)를 결정론적 모듈로 억압하는 프레임워크.

**구조:**
20가지 LLM 결함 → 9개 근본 원인으로 환원 → 각 원인별 방어 모듈(RC1~RC9) 구현.
이 9개 모듈을 PRPAO(인지-추론-행동-관찰-출력) 루프의 훅으로 배치.

**지금 함정:**
모든 방어 모듈(철창)은 완성됐지만, 실제 LLM을 호출하는 코드(`_phase_act()`)가 `# TODO`.
여기만 채우면 전체 파이프라인이 관통한다.

**확정된 설계 결정:**
1. Self-Consistency N=3 (파괴적 액션 시 N=5)
2. LATS 전환 3회 실패
3. Z3는 Pydantic Field만 (Phase 1)
4. AIR 동적 합성은 나중에
