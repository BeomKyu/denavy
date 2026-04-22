# Research Module Map

`docs/research`는 theory를 구현 가능한 설계로 연결하기 위한 외부 조사 레이어다.

## 역할

- 오픈소스 프레임워크와 구현 패턴을 비교한다.
- Denavy가 채택하거나 버릴 기술 선택지를 정리한다.
- theory 문서의 주장에 대해 실무적 근거를 제공한다.

## 문서 구성

- [open_source_guide.md](/C:/syszone_project/ui_design/docs/research/open_source_guide.md)
  - 개인 개발자/소규모 환경에서 쓸 수 있는 오픈소스 통제 장치를 조사한 문서.
- [orchestration_patterns.md](/C:/syszone_project/ui_design/docs/research/orchestration_patterns.md)
  - 에이전트 실행 루프, 프레임워크 토폴로지, 가드레일 배치 패턴을 조사한 문서.

## 읽는 법

- theory를 먼저 읽고 research를 본다.
- research의 기술 선택은 theory의 failure model을 해결하는지 기준으로 읽는다.
- research 문서의 세부 기술은 계약 문서가 생기면 그쪽으로 승격하거나 폐기한다.
