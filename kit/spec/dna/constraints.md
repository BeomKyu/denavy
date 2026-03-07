[Byeorim v1.4]
@CONSTRAINTS

# === 기술 스택 제약 ===
# 프로젝트에서 사용하는 언어, 프레임워크, 런타임 버전 등을 명시한다.

# lang: Python 3.12
# framework: FastAPI
# db: PostgreSQL 16
# runtime: Node 20 LTS

# === 보안 정책 ===
# 절대 위반해서는 안 되는 보안 규칙을 BAN으로 선언한다.

# BAN SQL_직접_문자열_결합
# BAN 하드코딩된_시크릿_키
# BAN eval()_또는_exec()_사용

# === API 호환성 ===
# 외부 API 버전, 엔드포인트, 인증 방식 등을 기록한다.

# url api_v2 = https://api.example.com/v2
# MUST API_응답_타임아웃 < 30s

# === 물리적 제약 ===
# 메모리, 디스크, 네트워크 등 인프라 제약을 명시한다.

# MUST 컨테이너_메모리 < 512MB
# MUST 응답_시간 < 200ms
