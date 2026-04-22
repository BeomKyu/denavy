# Denavy Docs Architecture

이 문서 집합은 코드베이스처럼 설계한다. 각 문서는 단일 책임을 가지며, 상위 문서는 하위 문서를 참조할 수 있어도 그 반대는 금지한다.

## 목적

Denavy의 출발점은 "AI를 믿지 않는다"는 판단이다. 따라서 문서 체계도 낭만적 선언문이 아니라, 문제 정의에서 원인 모델로, 원인 모델에서 구현 연구로 내려가는 결정론적 구조를 따라야 한다.

## 구조

### Layer 0. Directive
- [00_prime_directive.md](/C:/syszone_project/ui_design/docs/theory/00_prime_directive.md)
- 시스템의 존재 이유와 최상위 제약만 정의한다.
- 해결책 카탈로그를 쓰지 않는다.

### Layer 1. Failure Model
- [01_20_defects.md](/C:/syszone_project/ui_design/docs/theory/01_20_defects.md)
- 관찰 가능한 실패 증상만 정의한다.
- 해결책이나 구현 기술은 쓰지 않는다.

### Layer 2. Causal Model
- [02_9_root_causes.md](/C:/syszone_project/ui_design/docs/theory/02_9_root_causes.md)
- 왜 이런 실패가 반복되는지 설명하는 근본 원인 모델이다.
- 20개 결함을 9개 원인으로 압축한다.

### Layer 3. Research Base
- [research/README.md](/C:/syszone_project/ui_design/docs/research/README.md)
- 공개 사례, 프레임워크, 구현 기술 조사 결과를 보관한다.
- theory를 대체하지 않고 theory를 뒷받침한다.

## 읽는 순서

1. [00_prime_directive.md](/C:/syszone_project/ui_design/docs/theory/00_prime_directive.md)
2. [01_20_defects.md](/C:/syszone_project/ui_design/docs/theory/01_20_defects.md)
3. [02_9_root_causes.md](/C:/syszone_project/ui_design/docs/theory/02_9_root_causes.md)
4. [research/README.md](/C:/syszone_project/ui_design/docs/research/README.md)

## 문서 설계 원칙

- 응집도: 한 문서는 하나의 질문에만 답한다.
- 결합도: 같은 설명을 여러 문서에 반복하지 않는다.
- 추적성: 상위 문장의 근거가 필요하면 research 문서로 내려간다.
- 확장성: 이후 계약, 실행기, UI 문서는 이 구조 아래에 추가한다.

## 추가 규칙

- theory 문서는 "왜 필요한가"를 말한다.
- research 문서는 "무엇을 참고할 수 있는가"를 말한다.
- 구현 계약 문서는 아직 만들지 않는다. 먼저 failure model과 root cause model을 고정한다.
