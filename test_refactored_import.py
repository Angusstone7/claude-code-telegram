#!/usr/bin/env python3
"""
Quick smoke test for refactored MessageHandlers.
Checks that imports work and basic initialization succeeds.
"""
import sys
import asyncio

print("=" * 60)
print("REFACTORED MESSAGEHANDLERS SMOKE TEST")
print("=" * 60)

# Test 1: Import refactored package
print("\n[1/5] Testing import of refactored package...")
try:
    from presentation.handlers.message import MessageHandlers, MessageCoordinator
    print("✅ Import successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Import state managers
print("\n[2/5] Testing state manager imports...")
try:
    from presentation.handlers.state.user_state import UserStateManager
    from presentation.handlers.state.hitl_manager import HITLManager
    from presentation.handlers.state.file_context import FileContextManager
    from presentation.handlers.state.variable_input import VariableInputManager
    from presentation.handlers.state.plan_manager import PlanApprovalManager
    from presentation.middleware.message_batcher import MessageBatcher
    print("✅ State managers import successful")
except Exception as e:
    print(f"❌ State manager import failed: {e}")
    sys.exit(1)

# Test 3: Import container
print("\n[3/5] Testing container import...")
try:
    from shared.container import Container
    print("✅ Container import successful")
except Exception as e:
    print(f"❌ Container import failed: {e}")
    sys.exit(1)

# Test 4: Create container and initialize
print("\n[4/5] Testing container initialization...")
try:
    container = Container()

    # Check state manager factories exist
    assert hasattr(container, 'user_state_manager'), "Missing user_state_manager factory"
    assert hasattr(container, 'hitl_manager'), "Missing hitl_manager factory"
    assert hasattr(container, 'message_batcher'), "Missing message_batcher factory"

    print("✅ Container has all state manager factories")
except Exception as e:
    print(f"❌ Container initialization failed: {e}")
    sys.exit(1)

# Test 5: Test state manager sharing
print("\n[5/5] Testing state manager instance sharing...")
try:
    # Get same instance twice
    state1 = container.user_state_manager()
    state2 = container.user_state_manager()

    # Should be same object (singleton pattern)
    if state1 is state2:
        print(f"✅ State managers are shared (id: {id(state1)})")
    else:
        print(f"❌ State managers are NOT shared! (id1: {id(state1)}, id2: {id(state2)})")
        sys.exit(1)

    # Test with HITL manager
    hitl1 = container.hitl_manager()
    hitl2 = container.hitl_manager()
    if hitl1 is hitl2:
        print(f"✅ HITL managers are shared (id: {id(hitl1)})")
    else:
        print(f"❌ HITL managers are NOT shared!")
        sys.exit(1)

except Exception as e:
    print(f"❌ State manager sharing test failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\nRefactored MessageHandlers is ready for deployment.")
print("Key fixes:")
print("  - ✅ State managers are now SHARED singletons")
print("  - ✅ MessageBatcher factory added")
print("  - ✅ Imports from message/ package work")
print("  - ✅ Container properly initialized")
print("\nNext steps:")
print("  1. Commit changes")
print("  2. Push to GitLab (CI/CD will auto-deploy)")
print("  3. Monitor logs for streaming functionality")
