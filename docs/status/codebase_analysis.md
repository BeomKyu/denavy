# Denavy 코드베이스 현황 분석

> 분석 시점: 2026-03-29
> 분석 근거: 전체 소스코드, 리서치 문서, 이전 AI 구현 보고서, 평가자 피드백

---

## 완성도

```
9개 RC 방어 모듈 (192 tests)    ████████████████████ 100%
Z3 Bridge (Pydantic→Z3)         ████████████████████ 100%
PRPAO 오케스트레이터 뼈대        ████████░░░░░░░░░░░░  40%
LiteLLM Provider                ██████████████░░░░░░  70%
CLI (check/status/run)          ██████████████░░░░░░  70%
Act Phase (실제 LLM 호출)       ░░░░░░░░░░░░░░░░░░░░   0%
파일 적용 로직 (diff→file)      ░░░░░░░░░░░░░░░░░░░░   0%
RC7 Git TX 오케스트레이터 연결   ░░░░░░░░░░░░░░░░░░░░   0%
시스템 프롬프트                  ░░░░░░░░░░░░░░░░░░░░   0%
```

---

## 구현 완료 목록

### 9개 RC 방어 모듈 (denavy/rc1~rc9/)

| 모듈 | 파일 | 억압 결함 | 테스트 |
|------|------|----------|--------|
| RC1 | `rc1_optimization_pathology/pydantic_envelope.py` | 게으름(1), 아부(2) | 24개 |
| RC2-A | `rc2_autoregressive_bias/esaa.py` | 폭주(7) | 25개 (합산) |
| RC2-B | `rc2_autoregressive_bias/ast_parser.py` | 표류(11) | |
| RC3 | `rc3_attention_collapse/context_sidecar.py` | 기억상실(3), 토큰낭비(4), 덮어쓰기(5) | 21개 |
| RC4 | `rc4_epistemic_disconnect/sandbox_ocap.py` | 환각(6), 허위근거(9), 자원남용(15) | 13개 |
| RC5 | `rc5_tom_deficit/fsm_router.py` | 역할침범(16), 정보은닉실패(17) | 22개 |
| RC6 | `rc6_game_dynamics/consensus.py` | 사회적태만(18), 집단사고(20) | 16개 |
| RC7 | `rc7_network_entropy/transaction.py` | 무질서(8), 데드락(10) | 18개 |
| RC8 | `rc8_deductive_collapse/z3_verifier.py` | 가짜논리(12), 궤적이탈(13), 표면검증(14) | 19개 |
| RC9 | `rc9_security_collapse/intent_shield_defense.py` | 프롬프트감염(19) | 18개 |

### 인프라 모듈

| 모듈 | 파일 | 역할 |
|------|------|------|
| 오케스트레이터 | `orchestrator.py` | PRPAO 루프 뼈대 (Act가 TODO) |
| LLM Provider | `litellm_provider.py` | litellm + instructor 래핑 |
| Z3 Bridge | `rc8_deductive_collapse/z3_bridge.py` | Pydantic Field → Z3 자동변환 |
| 파이프라인 | `pipeline.py` | 9중 Fail-Fast 체인 (구형, orchestrator가 대체) |
| 설정 | `config.py` | Pydantic BaseSettings |
| 프로토콜 | `protocols.py` | 공통 인터페이스 |
| CLI | `__main__.py` | check / status / run |

---

## 갭 분석: 리서치 비전 vs 현재 코드

리서치 문서(orchestration_patterns.md)의 PRPAO 훅 배치도와 orchestrator.py 대조:

```
리서치 비전                       현재 구현               갭
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pre-hook (인지)
  RC9: 입력 보안                   ✅ _phase_perceive()    —
  RC3: 컨텍스트 준비               ✅ 프로젝트 인덱싱       —

In-process (추론)
  RC5: FSM 상태 검증               ✅ _phase_reason()      —
  RC4: 도구 검증                   ⚠️ 뼈대만               호출 시점 검증

Execution (행동)
  RC1: 구조화 LLM 호출             ❌ # TODO               LLM 호출 + 파싱
  RC2: 코드 구조 검증              ❌ 연결 안 됨            생성 코드 검증

Verification (관찰)
  RC8: Z3 논리 증명                ✅ _phase_observe()     Z3 Bridge 연결
  RC6: Self-Consistency            ❌ 향후                 N=3 다수결

Post-hook (출력)
  RC7: Git TX 적용/롤백            ❌ 연결 안 됨            diff 적용 + 커밋
```

---

## 확정된 아키텍처 결정 4가지

평가자 피드백 기반으로 확정된 설계 결정:

1. **RC6 Self-Consistency 호출 수**: N=3 기본, 파괴적 액션(`delete`/`modify`) 시 N=5
2. **LATS 전환 임계치**: 3회 연속 실패 → 트리 탐색 에스컬레이션
3. **Z3 자동 추출 범위**: Pydantic Field만 (Phase 1). 코드 if/else는 V2
4. **AIR 사고 대응**: 즉시 롤백(RC7)은 지금, 동적 가드레일 합성은 나중에

---

## 다음 단계 (우선순위 순)

### 🔴 즉시 (에이전트가 실제로 돌아가게)

1. **시스템 프롬프트 작성** — LLM이 IntentionPayload JSON을 올바르게 생성하게 유도
2. **`_phase_act()` 완성** — `_build_prompt()` + `LiteLLMProvider.complete_structured()` 연결
3. **파일 적용 로직** — `IntentionPayload.code_changes` diff → 실제 파일 적용
4. **RC7 Git TX 통합** — `TransactionManager` 안에서 파일 적용 + 테스트 실행

### 🟡 중요

5. **Reflexion 피드백 주입** — 실패 사유를 다음 LLM 프롬프트에 포함
6. **RC2 AST 검증 연결** — 생성된 코드의 구조적 건전성 검사
7. **RC6 Self-Consistency** — N=3 다수결 구현

### 🟢 V2 (나중에)

8. LATS 에스컬레이션
9. AIR 동적 가드레일 합성
10. LLM-Sym (Z3 Phase 2: 코드 if/else → Z3)
