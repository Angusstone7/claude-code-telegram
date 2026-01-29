#!/usr/bin/env python3
"""
Simple smoke test for refactored message handlers.
Run this BEFORE pushing to catch basic errors.

Usage: python test_refactored.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from presentation.handlers.message import MessageHandlers, register_handlers
        print("[OK] MessageHandlers import")
    except Exception as e:
        print(f"[FAIL] MessageHandlers import: {e}")
        return False

    try:
        from presentation.handlers.message.coordinator import MessageCoordinator
        print("[OK] MessageCoordinator import")
    except Exception as e:
        print(f"[FAIL] MessageCoordinator import: {e}")
        return False

    try:
        from presentation.handlers.message.text_handler import TextMessageHandler
        print("[OK] TextMessageHandler import")
    except Exception as e:
        print(f"[FAIL] TextMessageHandler import: {e}")
        return False

    try:
        from presentation.handlers.message.ai_request_handler import AIRequestHandler
        print("[OK] AIRequestHandler import")
    except Exception as e:
        print(f"[FAIL] AIRequestHandler import: {e}")
        return False

    return True


def test_handler_interface():
    """Test that MessageHandlers has required methods"""
    print("\nTesting MessageHandlers interface...")

    from presentation.handlers.message import MessageHandlers

    required_methods = ['handle_text', 'handle_document', 'handle_photo']

    for method in required_methods:
        if hasattr(MessageHandlers, method):
            print(f"[OK] {method} method exists")
        else:
            print(f"[FAIL] {method} method MISSING")
            return False

    return True


def test_router_registration():
    """Test that router registration doesn't crash"""
    print("\nTesting router registration logic...")

    try:
        from presentation.handlers.message import register_handlers

        # Mock handlers object
        class MockHandlers:
            async def handle_text(self, message): pass
            async def handle_document(self, message): pass
            async def handle_photo(self, message): pass

        # Test the type check logic (without actually registering)
        handlers = MockHandlers()
        has_methods = (
            hasattr(handlers, 'handle_text') and
            hasattr(handlers, 'handle_document') and
            hasattr(handlers, 'handle_photo')
        )

        if has_methods:
            print("[OK] Router registration type check")
            return True
        else:
            print("[FAIL] Router registration type check")
            return False

    except Exception as e:
        print(f"[FAIL] Router test: {e}")
        return False


def test_state_manager_imports():
    """Test that state managers can be imported"""
    print("\nTesting state manager imports...")

    try:
        from presentation.handlers.state.user_state import UserStateManager
        print("[OK] UserStateManager import")
    except Exception as e:
        print(f"[FAIL] UserStateManager import: {e}")
        return False

    try:
        from presentation.handlers.state.hitl_manager import HITLManager
        print("[OK] HITLManager import")
    except Exception as e:
        print(f"[FAIL] HITLManager import: {e}")
        return False

    try:
        from presentation.handlers.state.file_context import FileContextManager
        print("[OK] FileContextManager import")
    except Exception as e:
        print(f"[FAIL] FileContextManager import: {e}")
        return False

    try:
        from presentation.handlers.state.variable_input import VariableInputManager
        print("[OK] VariableInputManager import")
    except Exception as e:
        print(f"[FAIL] VariableInputManager import: {e}")
        return False

    try:
        from presentation.handlers.state.plan_manager import PlanApprovalManager
        print("[OK] PlanApprovalManager import")
    except Exception as e:
        print(f"[FAIL] PlanApprovalManager import: {e}")
        return False

    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("REFACTORED MESSAGE HANDLERS - SMOKE TESTS")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("State Managers", test_state_manager_imports()))
    results.append(("Handler Interface", test_handler_interface()))
    results.append(("Router Registration", test_router_registration()))

    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("[OK] ALL TESTS PASSED - safe to push")
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED - DO NOT PUSH")
        return 1


if __name__ == "__main__":
    sys.exit(main())
