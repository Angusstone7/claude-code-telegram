"""
Claude Code CLI Diagnostics

Run comprehensive tests to diagnose why Claude Code CLI isn't working.
"""

import asyncio
import os
import logging
import subprocess

logger = logging.getLogger(__name__)


async def run_diagnostics(claude_path: str = "claude") -> dict:
    """
    Run comprehensive diagnostics on Claude Code CLI.
    Returns dict with results of each test.
    """
    results = {
        "tests": [],
        "summary": "",
        "working": False
    }

    # Test 1: Check if claude binary exists
    test1 = await _test_binary_exists(claude_path)
    results["tests"].append(test1)

    # Test 2: Get version
    test2 = await _test_version(claude_path)
    results["tests"].append(test2)

    # Test 3: Get help output
    test3 = await _test_help(claude_path)
    results["tests"].append(test3)

    # Test 4: Check environment
    test4 = _test_environment()
    results["tests"].append(test4)

    # Test 5: Simple prompt test (with timeout)
    test5 = await _test_simple_prompt(claude_path)
    results["tests"].append(test5)

    # Generate summary
    passed = sum(1 for t in results["tests"] if t["passed"])
    total = len(results["tests"])
    results["summary"] = f"Passed {passed}/{total} tests"
    results["working"] = all(t["passed"] for t in results["tests"])

    return results


async def _test_binary_exists(claude_path: str) -> dict:
    """Test if claude binary is accessible"""
    test = {
        "name": "Binary exists",
        "passed": False,
        "output": "",
        "error": ""
    }

    try:
        result = subprocess.run(
            ["which", claude_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            test["passed"] = True
            test["output"] = result.stdout.strip()
        else:
            test["error"] = f"Binary not found: {result.stderr}"
    except FileNotFoundError:
        # Windows doesn't have 'which', try 'where' or just run --version
        try:
            result = subprocess.run(
                [claude_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            test["passed"] = result.returncode == 0
            test["output"] = result.stdout.strip() if result.returncode == 0 else ""
            test["error"] = result.stderr.strip() if result.returncode != 0 else ""
        except Exception as e:
            test["error"] = str(e)
    except Exception as e:
        test["error"] = str(e)

    return test


async def _test_version(claude_path: str) -> dict:
    """Test claude --version"""
    test = {
        "name": "Version check",
        "passed": False,
        "output": "",
        "error": ""
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            claude_path, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        test["output"] = stdout.decode().strip()
        test["error"] = stderr.decode().strip()
        test["passed"] = proc.returncode == 0 and len(test["output"]) > 0

    except asyncio.TimeoutError:
        test["error"] = "Timeout after 10 seconds"
    except Exception as e:
        test["error"] = str(e)

    return test


async def _test_help(claude_path: str) -> dict:
    """Test claude --help"""
    test = {
        "name": "Help output",
        "passed": False,
        "output": "",
        "error": ""
    }

    try:
        proc = await asyncio.create_subprocess_exec(
            claude_path, "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        output = stdout.decode()
        test["output"] = output[:500] + "..." if len(output) > 500 else output
        test["error"] = stderr.decode().strip()
        test["passed"] = proc.returncode == 0 and len(output) > 100

    except asyncio.TimeoutError:
        test["error"] = "Timeout after 10 seconds"
    except Exception as e:
        test["error"] = str(e)

    return test


def _test_environment() -> dict:
    """Check environment variables"""
    test = {
        "name": "Environment",
        "passed": False,
        "output": "",
        "error": ""
    }

    env_info = []

    # Check ANTHROPIC_API_KEY
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        env_info.append(f"ANTHROPIC_API_KEY: set ({len(api_key)} chars, starts with {api_key[:10]}...)")
        test["passed"] = True
    else:
        env_info.append("ANTHROPIC_API_KEY: NOT SET!")
        test["error"] = "ANTHROPIC_API_KEY is not set"

    # Check other relevant env vars
    env_info.append(f"HOME: {os.environ.get('HOME', 'not set')}")
    env_info.append(f"PATH: {os.environ.get('PATH', 'not set')[:100]}...")
    env_info.append(f"TERM: {os.environ.get('TERM', 'not set')}")
    env_info.append(f"CI: {os.environ.get('CI', 'not set')}")

    test["output"] = "\n".join(env_info)

    return test


async def _test_simple_prompt(claude_path: str) -> dict:
    """Test a simple prompt with short timeout"""
    test = {
        "name": "Simple prompt test",
        "passed": False,
        "output": "",
        "error": ""
    }

    try:
        env = os.environ.copy()
        env["CI"] = "true"
        env["TERM"] = "dumb"

        proc = await asyncio.create_subprocess_exec(
            claude_path, "-p", "Say just 'OK'", "--output-format", "text",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        # Short timeout - 30 seconds should be enough for a simple response
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            test["output"] = stdout.decode()[:500]
            test["error"] = stderr.decode()[:500]
            test["passed"] = proc.returncode == 0 and len(test["output"]) > 0

            if not test["passed"] and not test["output"] and not test["error"]:
                test["error"] = f"No output received, returncode={proc.returncode}"

        except asyncio.TimeoutError:
            test["error"] = "Timeout after 30 seconds - CLI hangs without producing output"
            # Kill the process
            proc.kill()
            await proc.wait()

    except Exception as e:
        test["error"] = str(e)

    return test


async def run_and_log_diagnostics(claude_path: str = "claude"):
    """Run diagnostics and log results"""
    logger.info("=" * 50)
    logger.info("CLAUDE CODE CLI DIAGNOSTICS")
    logger.info("=" * 50)

    results = await run_diagnostics(claude_path)

    for test in results["tests"]:
        status = "✓ PASS" if test["passed"] else "✗ FAIL"
        logger.info(f"\n{status}: {test['name']}")
        if test["output"]:
            for line in test["output"].split("\n")[:10]:
                logger.info(f"  stdout: {line}")
        if test["error"]:
            for line in test["error"].split("\n")[:5]:
                logger.warning(f"  stderr: {line}")

    logger.info(f"\n{'=' * 50}")
    logger.info(f"SUMMARY: {results['summary']}")
    logger.info(f"CLI Working: {results['working']}")
    logger.info("=" * 50)

    return results


def format_diagnostics_for_telegram(results: dict) -> str:
    """Format diagnostics results for Telegram message"""
    lines = ["🔍 **Claude Code Diagnostics**\n"]

    for test in results["tests"]:
        emoji = "✅" if test["passed"] else "❌"
        lines.append(f"{emoji} **{test['name']}**")

        if test["output"]:
            output_short = test["output"][:200].replace("\n", " ")
            lines.append(f"   `{output_short}`")

        if test["error"]:
            error_short = test["error"][:200].replace("\n", " ")
            lines.append(f"   ⚠️ {error_short}")

        lines.append("")

    lines.append(f"**Summary:** {results['summary']}")

    return "\n".join(lines)
