# Denavy

> 결정론적 LLM 에이전트 통제 아키텍처 — 비대칭 방어 파이프라인

확률론적 LLM의 20가지 결함을 9개의 근본 원인(Root Cause)으로 환원하고,
각 원인을 결정론적 모듈로 억압하는 에이전트 통제 프레임워크.

## 아키텍처

PRPAO (인지-추론-계획-행동-관찰) 생명주기 기반 오케스트레이터:

```
Perceive ─→ Reason ─→ Act ─→ Observe ─→ Response
   │           │        │        │          │
  RC9         RC5      RC1      RC8        RC7
  RC3         RC4      RC2      RC6     (Git TX)
```

## 9개 방어 모듈

| 모듈 | 억압 대상 | 메커니즘 |
|------|----------|---------|
| RC1 | 게으름, 아부 | Pydantic JSON 봉투 강제 |
| RC2 | 폭주, 표류 | 이벤트 소싱(ESAA) + AST 구조 검증 |
| RC3 | 기억상실, 토큰낭비 | CQRS 컨텍스트 사이드카 |
| RC4 | 환각 도구 호출 | OCap 도구 화이트리스트 |
| RC5 | 역할 침범 | FSM 상태 기계 라우터 |
| RC6 | 집단사고 | 합의 투표 프로토콜 |
| RC7 | 무질서, 데드락 | Git 유사-원자적 트랜잭션 |
| RC8 | 가짜 논리 | Z3 SMT 논리 증명 |
| RC9 | 프롬프트 감염 | IntentShield 보안 |

## 설치

```bash
uv sync
cp .env.example .env
# .env에서 DENAVY_API_KEY 설정
```

## 사용법

```bash
# 설정 확인
python -m denavy check

# 모듈 상태
python -m denavy status

# 에이전트 실행 (dry-run)
python -m denavy run "지시문" --dry-run

# 테스트
uv run pytest tests/ -v
```

## 프로젝트 구조

```
denavy/
├── denavy/              # 메인 패키지
│   ├── orchestrator.py  # PRPAO 오케스트레이터
│   ├── litellm_provider.py  # LLM API (litellm+instructor)
│   ├── pipeline.py      # Fail-Fast 검증 체인
│   ├── config.py        # 설정 (Pydantic Settings)
│   ├── protocols.py     # 공통 인터페이스
│   └── rc1~rc9/         # 9개 방어 모듈
├── tests/               # 192+ 테스트
├── docs/                # 이론 문서, 리서치, 아키텍처 다이어그램
└── data/                # 런타임 데이터
```

## 문서

[docs/README.md](docs/README.md)에서 읽는 순서와 맥락 복구 가이드를 확인하세요.

- **현재 상태**: [codebase_analysis.md](docs/status/codebase_analysis.md)
- **이론**: [제0원칙](docs/theory/00_prime_directive.md) → [20대 결함](docs/theory/01_20_defects.md) → [9대 근본 원인](docs/theory/02_9_root_causes.md)
- **설계**: [오픈소스 가이드](docs/research/open_source_guide.md) · [오케스트레이션 패턴](docs/research/orchestration_patterns.md)
