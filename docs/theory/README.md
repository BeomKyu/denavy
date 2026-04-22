# Theory Module Map

`docs/theory`는 Denavy의 철학과 진단 모델을 담는 코어 모듈이다.

## 모듈 구성

- [00_prime_directive.md](/C:/syszone_project/ui_design/docs/theory/00_prime_directive.md)
  - 최상위 목적과 금지선을 정의한다.
- [01_20_defects.md](/C:/syszone_project/ui_design/docs/theory/01_20_defects.md)
  - 현상 레벨의 실패 카탈로그다.
- [02_9_root_causes.md](/C:/syszone_project/ui_design/docs/theory/02_9_root_causes.md)
  - 실패를 낳는 구조적 원인 모델이다.

## 의존 규칙

- `00`은 어느 문서에도 의존하지 않는다.
- `01`은 `00`만 전제한다.
- `02`는 `00`, `01`만 전제한다.
- research 문서는 theory를 참조할 수 있지만, theory는 특정 research 결론에 종속되지 않는다.

## 사용 규칙

- 새 문서를 추가할 때는 먼저 "증상 문서인지, 원인 문서인지, 연구 문서인지"를 분류한다.
- 하나의 문서에 철학, 증상, 기술 솔루션을 동시에 섞지 않는다.
