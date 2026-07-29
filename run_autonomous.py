#!/usr/bin/env python3
"""
run_autonomous.py — Single entry point for the full autonomous coding pipeline.

    NL Prompt -> Validated Spec -> PLAN.md -> RUNBOOK.md -> Execute -> Report

USAGE (local execution):

    python3 run_autonomous.py \
        --prompt "Add a POST /notifications endpoint that sends email and push notifications. Accept recipient, subject, body, and priority. Return 202 with notification ID. Add integration tests." \
        --model qwen2.5-coder:7b-instruct \
        --provider ollama

USAGE (Docker-isolated execution — clean container, auto-destroyed):

    python3 run_autonomous.py \
        --prompt "..." \
        --model specforge-128k:latest \
        --provider ollama \
        --docker

USAGE (cloud model):

    python3 run_autonomous.py \
        --prompt "..." \
        --model anthropic/claude-sonnet-4 \
        --provider openrouter \
        --api-key $OPENROUTER_API_KEY

OPTIONS:
    --prompt       Natural language feature request (required)
    --output-dir   Where to write spec.yaml, PLAN.md, RUNBOOK.md (default: ./output/<task_id>)
    --model        LLM model name (default: qwen2.5-coder:7b-instruct)
    --provider     LLM provider: ollama|openrouter|openai|custom (default: ollama)
    --api-key      API key (for cloud providers; not needed for Ollama)
    --docker       Run execution inside an isolated Docker container
    --max-retries  Max retries per command (default: 3)
    --timeout      Command timeout in seconds (default: 120)
    --verbose      Print detailed execution output
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


# Path to the autonomous_execute.py script in the Hermes skill
AUTONOMOUS_SCRIPT = Path.home() / ".hermes" / "skills" / "software-development" / "command-runway-autonomous" / "scripts" / "autonomous_execute.py"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Single entry point: NL prompt -> spec -> plan -> runbook -> execute -> report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python3 run_autonomous.py --prompt \"Add health endpoint\" --model qwen2.5-coder:7b-instruct\n"
               "  python3 run_autonomous.py --prompt \"...\" --model specforge-128k:latest --docker\n"
               "  python3 run_autonomous.py --prompt \"...\" --model anthropic/claude-sonnet-4 --provider openrouter --api-key sk-...\n"
    )
    parser.add_argument("--prompt", type=str, required=True,
                        help="Natural language feature request")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory (default: ./output/<task_id>)")

    # LLM configuration
    parser.add_argument("--model", type=str, default="qwen2.5-coder:7b-instruct",
                        help="LLM model name (default: qwen2.5-coder:7b-instruct)")
    parser.add_argument("--provider", type=str, default="ollama",
                        choices=["ollama", "openrouter", "openai", "custom"],
                        help="LLM provider (default: ollama)")
    parser.add_argument("--api-key", type=str, default="",
                        help="API key (for cloud providers; not needed for Ollama)")
    parser.add_argument("--base-url", type=str, default="",
                        help="Custom LLM base URL (overrides provider default)")

    # Execution options
    parser.add_argument("--docker", action="store_true", default=False,
                        help="Run execution inside an isolated Docker container")
    parser.add_argument("--max-retries", type=int, default=3,
                        help="Max retries per command (default: 3)")
    parser.add_argument("--timeout", type=int, default=120,
                        help="Command timeout in seconds (default: 120)")
    parser.add_argument("--executor", type=str, default="python",
                        choices=["python", "hermes", "opencode"],
                        help="Execution backend (default: python)")

    # Executor model (optional — defaults to --model if not set)
    parser.add_argument("--exec-model", type=str, default=None,
                        help="Model for executor stage (default: same as --model)")
    parser.add_argument("--exec-provider", type=str, default=None,
                        choices=["ollama", "openrouter", "openai", "custom"],
                        help="Provider for executor stage (default: same as --provider)")

    # Stale file cleanup
    parser.add_argument("--fresh", action="store_true", default=False,
                        help="Remove output directory before running (cleans stale files)")
    parser.add_argument("--verbose", "-v", action="store_true", default=False,
                        help="Print detailed execution output")
    parser.add_argument("--clean", action="store_true", default=False,
                        help="Clean up generated feature code after execution (removes src/<task_id>/)")
    parser.add_argument("--no-clean", action="store_true", default=False,
                        help="Do not remove feature code even on failure (for debugging)")

    return parser.parse_args()


def resolve_base_url(provider: str, base_url: str) -> str:
    """Resolve the LLM base URL based on provider."""
    if base_url:
        return base_url
    if provider == "ollama":
        return "http://localhost:11434/v1"
    elif provider == "openrouter":
        return "https://openrouter.ai/api/v1"
    elif provider == "openai":
        return "https://api.openai.com/v1"
    else:
        return os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")


def resolve_output_dir(prompt: str, output_dir: str) -> Path:
    """Derive output directory from prompt if not specified."""
    if output_dir:
        return Path(output_dir)

    # Generate a task_id from the prompt (first few words, kebab-case)
    import re
    words = re.sub(r'[^a-zA-Z0-9\s]', '', prompt.lower()).split()[:4]
    task_id = '-'.join(words) if words else 'autonomous-task'
    return Path("output") / task_id


def main():
    args = parse_args()

    # Verify the autonomous_execute.py script exists
    # Check both the Hermes skill path and the repo-local path
    repo_script = Path(__file__).resolve().parent / "skills" / "software-development" / "command-runway-autonomous" / "scripts" / "autonomous_execute.py"
    autonomous_script = AUTONOMOUS_SCRIPT if AUTONOMOUS_SCRIPT.exists() else repo_script
    if not autonomous_script.exists():
        print(f"ERROR: autonomous_execute.py not found at:")
        print(f"  {AUTONOMOUS_SCRIPT}")
        print(f"  {repo_script}")
        print("Install the command-runway-autonomous skill first.")
        sys.exit(1)

    # Resolve output directory
    output_path = resolve_output_dir(args.prompt, args.output_dir)

    # --fresh: remove stale output before running
    if args.fresh and output_path.exists():
        import shutil
        shutil.rmtree(output_path)
        print(f"  [fresh] Removed stale output: {output_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    # Resolve LLM config
    base_url = resolve_base_url(args.provider, args.base_url)
    api_key = args.api_key or os.environ.get("LLM_API_KEY", "")
    if args.provider == "ollama" and not api_key:
        api_key = "ollama"  # Ollama ignores this but some clients require non-empty

    # Build the command to invoke autonomous_execute.py
    cmd = [
        sys.executable,
        str(AUTONOMOUS_SCRIPT),
        "--prompt", args.prompt,
        "--output-dir", str(output_path),
        "--output", "all",  # Full pipeline: spec + plan + runbook + execution
        "--executor", args.executor,
        "--max-retries", str(args.max_retries),
        "--timeout", str(args.timeout),
        "--llm-model", args.model,
        "--llm-provider", args.provider,
        "--llm-api-key", api_key,
        "--llm-base-url", base_url,
    ]

    if args.docker:
        cmd.append("--docker")

    if args.verbose:
        cmd.append("--yolo")  # Auto-approve (passed to Hermes if --executor hermes)

    # Print the pipeline configuration
    print("=" * 70)
    print("AUTONOMOUS PIPELINE")
    print("=" * 70)
    print(f"  Prompt:    {args.prompt[:80]}{'...' if len(args.prompt) > 80 else ''}")
    print(f"  Model:     {args.model}")
    print(f"  Provider:  {args.provider}")
    print(f"  Base URL:  {base_url}")
    if args.exec_model:
        print(f"  Exec Model:    {args.exec_model}")
        print(f"  Exec Provider: {args.exec_provider or args.provider}")
    print(f"  Docker:    {'YES (isolated container)' if args.docker else 'NO (host execution)'}")
    print(f"  Output:    {output_path}")
    print(f"  Executor:  {args.executor}")
    print(f"  Retries:   {args.max_retries}")
    print(f"  Timeout:   {args.timeout}s")
    print(f"  Script:    {autonomous_script}")
    print("=" * 70)
    print()

    # Set environment variables for LLM config (autonomous_execute.py reads these)
    env = os.environ.copy()
    env["LLM_BASE_URL"] = base_url
    env["LLM_MODEL"] = args.model
    env["LLM_API_KEY"] = api_key

    # Build the command to invoke autonomous_execute.py
    cmd = [
        sys.executable,
        str(autonomous_script),
        "--prompt", args.prompt,
        "--output-dir", str(output_path),
        "--output", "all",  # Full pipeline: spec + plan + runbook + execution
        "--executor", args.executor,
        "--max-retries", str(args.max_retries),
        "--timeout", str(args.timeout),
        "--llm-model", args.model,
        "--llm-provider", args.provider,
        "--llm-api-key", api_key,
        "--llm-base-url", base_url,
    ]

    if args.docker:
        cmd.append("--docker")

    # Pass executor model/provider if different from spec model
    if args.exec_model:
        cmd.extend(["--exec-model", args.exec_model])
    if args.exec_provider:
        cmd.extend(["--exec-provider", args.exec_provider])

    if args.verbose:
        cmd.append("--yolo")  # Auto-approve (passed to Hermes if --executor hermes)

    if args.clean:
        cmd.append("--clean")
    if args.no_clean:
        cmd.append("--no-clean")

    # Execute the pipeline
    try:
        result = subprocess.run(cmd, env=env)
        exit_code = result.returncode
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        exit_code = 130

    if exit_code == 0:
        print(f"\n{'=' * 70}")
        print("PIPELINE COMPLETE")
        print(f"{'=' * 70}")
        print(f"  Spec:     {output_path}/spec.yaml")
        print(f"  Plan:     {output_path}/PLAN.md")
        print(f"  Runbook:  {output_path}/RUNBOOK.md")
        if args.docker:
            print(f"  (Docker container destroyed)")
    else:
        print(f"\n{'=' * 70}")
        print(f"PIPELINE FAILED (exit code {exit_code})")
        print(f"{'=' * 70}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
