"""
Denavy CLI 진입점
━━━━━━━━━━━━━━━
python -m denavy check    — 설정 확인
python -m denavy run "지시" — 에이전트 실행
python -m denavy status   — 모듈 상태 확인
"""

from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="denavy",
        description="결정론적 LLM 에이전트 통제 프레임워크",
    )
    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # check
    check_parser = subparsers.add_parser("check", help="설정 및 연결 확인")

    # status
    status_parser = subparsers.add_parser("status", help="모듈 상태 확인")

    # run
    run_parser = subparsers.add_parser("run", help="에이전트 실행")
    run_parser.add_argument("instruction", help="자연어 지시문")
    run_parser.add_argument(
        "--project", "-p", default=".", help="대상 프로젝트 경로"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="검증만 수행 (실제 적용 안 함)"
    )

    args = parser.parse_args()

    if args.command == "check":
        _cmd_check()
    elif args.command == "status":
        _cmd_status()
    elif args.command == "run":
        _cmd_run(args)
    else:
        parser.print_help()


def _cmd_check() -> None:
    """설정 및 연결 상태 확인."""
    from denavy.config import settings
    from denavy.litellm_provider import LiteLLMProvider

    print("=" * 50)
    print("  Denavy 설정 확인")
    print("=" * 50)
    print()

    # 설정값
    print(f"  모델:     {settings.default_model}")
    print(f"  API 키:   {'✅ 설정됨' if settings.api_key else '❌ 미설정'}")
    print(f"  API Base: {settings.api_base or '(기본값)'}")
    print(f"  데이터:   {settings.data_dir}")
    print(f"  재시도:   {settings.max_retry_on_reject}회")
    print()

    # LLM 연결
    provider = LiteLLMProvider()
    status = provider.check_connection()
    ready = status["ready"]
    print(f"  LLM 준비: {'✅ 준비됨' if ready else '❌ API 키를 설정하세요'}")
    if not ready:
        print()
        print("  설정 방법:")
        print("    1. copy .env.example .env")
        print("    2. .env 파일에서 DENAVY_API_KEY 값 입력")
    print()


def _cmd_status() -> None:
    """모듈 상태 확인."""
    from denavy.orchestrator import AgentOrchestrator

    print("=" * 50)
    print("  Denavy 모듈 상태")
    print("=" * 50)
    print()

    orch = AgentOrchestrator()
    orch._ensure_modules()

    modules = [
        ("RC1", "Pydantic Envelope", "rc1"),
        ("RC2", "AST Parser", "rc2_ast"),
        ("RC2", "ESAA Event Store", "rc2_esaa"),
        ("RC3", "Context Sidecar", "rc3_defense"),
        ("RC4", "Sandbox OCap", "rc4"),
        ("RC5", "FSM Router", "rc5_defense"),
        ("RC8", "Z3 Verifier", "rc8"),
        ("RC9", "IntentShield", "rc9"),
    ]

    for rc, name, key in modules:
        mod = orch._modules.get(key)
        enabled = mod.is_enabled() if mod else False
        status = "✅ 활성" if enabled else "❌ 비활성"
        print(f"  {rc:4s} {name:20s} {status}")

    print()
    print(f"  PRPAO 루프: 인지→추론→행동→관찰→출력")
    print(f"  재시도: {orch._max_retries}회 (Reflexion → LATS)")
    print()


def _cmd_run(args: argparse.Namespace) -> None:
    """에이전트 실행."""
    from pathlib import Path

    from denavy.litellm_provider import LiteLLMProvider
    from denavy.orchestrator import AgentOrchestrator

    project_path = Path(args.project).resolve()
    print(f"프로젝트: {project_path}")
    print(f"지시: {args.instruction}")
    print()

    provider = None
    if not args.dry_run:
        provider = LiteLLMProvider()
        status = provider.check_connection()
        if not status["ready"]:
            print("❌ API 키가 설정되지 않았습니다.")
            print("   denavy check 명령으로 설정을 확인하세요.")
            sys.exit(1)

    orch = AgentOrchestrator(
        llm_provider=provider,
        project_path=project_path,
    )

    result = orch.run(args.instruction)

    print(result.summary)
    if not result.success:
        print(f"  실패 단계: {result.phase.value}")
        print(f"  사유: {result.message}")
        for dr in result.defense_results:
            if dr.rejected:
                print(f"  ← {dr.module_name}: {dr.reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
