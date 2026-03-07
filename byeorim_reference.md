# 벼림(Byeorim) v1.4 퀵 레퍼런스

> 에이전트를 위한 메타 청사진 언어. 자연어의 모호함과 프로그래밍 언어의 노이즈를 동시에 제거한다.

## 3대 헌법

1. **Zero Noise:** `{}`, `,`, `""` 전면 불법화. 들여쓰기와 기호로만 승부.
2. **마찰 없는 타건:** 구조적 충돌 완벽 제거. 보편 수학 기호(`!=`, `==`, `<`, `>`)는 합법.
3. **3대 형태학 계급:** 기호의 생김새로 역할을 즉시 판별.

## 기호 총람

### 🅰️ 대문자 룬 — 거시 통제와 공간

| 기호 | 의미 | 예시 |
|---|---|---|
| `NOW` | 마일스톤 (과거 기억 버려라) | `NOW 2026-03-08` |
| `BAN` | 절대 금지 (치명적 흉터) | `BAN SQL_인젝션` |
| `OLD` | 더티 엔딩 (냅둬라) | `OLD 구형_결제_모듈` |
| `MUST` | 필수 제약 (위반 시 폭파) | `MUST amount > 0` |
| `PUB` | 외부 공개 | `PUB $App.Login:` |
| `TX` | 무결성 트랜잭션 결계 | `TX $DB.transfer:` |
| `FAIL` | 재난 수습 방벽 | `FAIL err:` |
| `UI` | 시각적 공간 껍질 | `UI login_box:` |
| `ST` | 최초 반응형 상태 선언 | `ST count: Int = 0` |
| `CLK` | 사용자 이벤트 방아쇠 | `CLK submit_btn:` |

### 🅱️ 방향성 화살표 — 미시 액션과 흐름

| 기호 | 의미 | 예시 |
|---|---|---|
| `<-` | 외부 I/O 견인 (찌르고 당겨옴) | `result <- $DB.query()` |
| `>/` | 동기 찌르기 (대기) | `>/ $DB.update()` |
| `/>` | 비동기 발사 (안 기다림) | `/> send_email()` |
| `//>` | 병렬 찌르기 (동시 발사) | `roles <- //> fetch()` |
| `\|>` | 파이프라인 (벽 뚫고 밀기) | `data \|> clean() \|> save()` |
| `=>` | 정상 반환 | `=> user_token` |
| `?=>` | 예외/부정 반환 (조기 종료) | `?=> Error(인증_실패)` |

### Ⓒ 닻과 연결고리 — 조용한 특수기호/소문자

| 기호 | 의미 | 예시 |
|---|---|---|
| `$` | 전역 식별자 (환각 방지) | `$Auth.User:` |
| `url` | 외부 참조 닻 | `url api = https://...` |
| `:` | 타입 명시 | `amount: Int = 0` |
| `( )` | 투명 데이터 캡슐 | `Error(결제_실패)` |
| `#` | 인간의 속삭임 (AI 무시) | `# 메모` |
| `-` | 리스트 글머리 | `- v1.0.0` |
| `=` | 메모리 할당/갱신 | `is_loading = true` |
| `&` | 인라인 배열 (AND) | `tags = auth & core` |
| `?` | 조건 분기 관문 | `? password_match:` |
| `*` | 반복 순회 | `* item in items:` |
| `use` | 의존성 주입 | `use $Security.Auth` |
| `::` | 상속 | `$Login :: $Base:` |
| `:+` | 구현 (Implements) | `$API :+ $Rest:` |
| `[ ]` | 칸반 상태 머신 | `[x] 완료_항목` |

## 칸반 상태 표기

| 표기 | 의미 |
|---|---|
| `[_]` | 대기 (Pending) |
| `[-]` | 진행 중 (In Progress) |
| `[x]` | 완료 (Done) |
| `[!]` | 실패/차단 (Blocked) |

## 예시

```text
NOW 2026-03-08 / v1.4
BAN 하드코딩된_시크릿_키

use $Security.Auth
url pg_api = https://api.pay.com

PUB $App.PaymentScreen :: $Base.Screen:

  ST amount: Int = 0
  ST is_loading: Bool = false

  UI payment_modal:

    CLK submit_btn:
      is_loading = true

      TX $DB.process_payment:
        MUST amount > 0
        cleaned_amt = amount |> abs() |> to_int()
        result <- $PG.request(cleaned_amt)
        ?=> result.status != SUCCESS:
          => Error(결제_실패_응답)
        /> $Log.save_history(result)

      FAIL err:
        is_loading = false
        => Error(err.msg)

      is_loading = false
      => result.receipt_id
```
