# Denavy

LLM 코딩 에이전트를 위한 멀티 에이전트 오케스트레이션 프로토콜.

비결정론적 AI 추론을 결정론적 SDLC에 안전하게 통합하는 **3단계 명세 주도형 파이프라인**.

## 구성

| 파일 | 역할 |
|---|---|
| `denavy_master_v4.0.md` | 마스터 아키텍처 명세서 (이론적 근거 및 전체 설계) |
| `byeorim_reference.md` | 벼림 v1.4 DSL 퀵 레퍼런스 |
| `kit/` | **드롭인 프로토콜 킷** — 타 프로젝트에 복사하여 사용 |

## 드롭인 사용법

### 1. kit 복사

```bash
cp -r kit/* /path/to/your/project/
```

> **참고:** `src/` 디렉토리는 킷에 포함되지 않음. 타겟 프로젝트에 이미 존재한다고 가정.

### 2. Git Hook 활성화 (최초 1회)

```bash
cd /path/to/your/project
git config core.hooksPath .githooks
```

> **⚠️ 주의:** 프로젝트가 Husky 등 기존 Git Hook 관리 도구를 사용 중이라면,
> `core.hooksPath` 설정이 기존 훅을 무효화할 수 있습니다.
> 이 경우 `.githooks/pre-commit`의 로직을 기존 훅 파일에 수동 병합하세요.

### 3. 프로젝트별 설정

- `spec/dna/coding_rules.md` — 코딩 컨벤션, 리뷰 규칙 등 작성
- `spec/dna/constraints.md` — 기술 스택, 보안 정책 등 작성

### 4. 에이전트 실행

IDE(Cursor, Claude Code 등)에서 에이전트가 `DENAVY.md`를 읽으면 자동으로 3단계 파이프라인을 따릅니다.

## Kit 구조

```
kit/
├── DENAVY.md                  마스터 시스템 프롬프트 (에이전트 헌법)
├── .denavy/
│   ├── state.md               FSM + Progress + Features 통합 상태 (SSOT)
│   └── reviewer_reports/      적대적 검증 리포트 보관소
├── .githooks/
│   └── pre-commit             FSM 상태 기반 spec/ 접근 차단
├── spec/
│   ├── dna/
│   │   ├── constraints.md     기술 제약조건 템플릿
│   │   └── coding_rules.md    코딩 컨벤션 템플릿
│   ├── spec.md                벼림 @SPEC 스켈레톤
│   └── test/
├── sandbox/
│   └── src_draft/             에이전트 격리 작업 공간
└── memory/
    └── episodic/              실행 로그 저장소
```

## 라이선스

Private
