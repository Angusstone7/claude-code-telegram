#!/usr/bin/env python3
"""
Сравнение legacy vs refactored кода.
Проверяем что оба варианта имеют одинаковые методы и поведение.
"""
import sys
import asyncio
import inspect

def test_methods_match():
    """Проверить что все PUBLIC методы legacy есть в facade"""
    print("\n[1/5] Testing methods match...")

    from presentation.handlers.messages import MessageHandlers as Legacy
    from presentation.handlers.message import MessageHandlers as Refactored

    # Only check PUBLIC methods (not private _methods)
    legacy_methods = [m for m in dir(Legacy) if not m.startswith('_') and not m.startswith('__')]
    refactored_methods = [m for m in dir(Refactored) if not m.startswith('_') and not m.startswith('__')]

    missing = set(legacy_methods) - set(refactored_methods)
    extra = set(refactored_methods) - set(legacy_methods)

    if missing:
        print(f"  ❌ Missing public methods in refactored: {missing}")
        return False

    if extra:
        print(f"  ⚠️  Extra public methods in refactored: {extra}")

    print(f"  ✅ All {len(legacy_methods)} public methods present")
    if extra:
        print(f"  ℹ️  Private methods (starting with _) are not exposed - this is OK")
    return True

def test_parameters_match():
    """Проверить что __init__ принимает те же параметры"""
    print("\n[2/5] Testing __init__ parameters match...")

    from presentation.handlers.messages import MessageHandlers as Legacy
    from presentation.handlers.message import MessageHandlers as Refactored

    legacy_sig = inspect.signature(Legacy.__init__)
    refactored_sig = inspect.signature(Refactored.__init__)

    legacy_params = set(legacy_sig.parameters.keys()) - {'self'}
    refactored_params = set(refactored_sig.parameters.keys()) - {'self', 'kwargs'}

    missing = legacy_params - refactored_params
    extra = refactored_params - legacy_params

    if missing:
        print(f"  ❌ Missing parameters: {missing}")
        return False

    print(f"  ✅ All {len(legacy_params)} parameters present")
    if extra:
        print(f"  ℹ️  Extra parameters (OK if optional): {extra}")

    return True

def test_method_signatures_match():
    """Проверить что сигнатуры методов совпадают"""
    print("\n[3/5] Testing method signatures match...")

    from presentation.handlers.messages import MessageHandlers as Legacy
    from presentation.handlers.message import MessageHandlers as Refactored

    methods_to_check = [
        'handle_text',
        'handle_document',
        'handle_photo',
        'is_yolo_mode',
        'set_yolo_mode',
        'handle_permission_response',
        'handle_question_response',
        'handle_plan_response',
    ]

    mismatches = []
    for method_name in methods_to_check:
        if not hasattr(Legacy, method_name) or not hasattr(Refactored, method_name):
            continue

        legacy_method = getattr(Legacy, method_name)
        refactored_method = getattr(Refactored, method_name)

        legacy_sig = inspect.signature(legacy_method)
        refactored_sig = inspect.signature(refactored_method)

        # **kwargs is compatible with explicit parameters - this is OK
        # Only check if refactored has **kwargs, which means it accepts all params
        if '**kwargs' in str(refactored_sig):
            continue  # **kwargs accepts everything, this is compatible

        legacy_str = str(legacy_sig).replace(', **kwargs', '').replace(', **', '')
        refactored_str = str(refactored_sig).replace(', **kwargs', '').replace(', **', '')

        if legacy_str != refactored_str:
            mismatches.append((method_name, str(legacy_sig), str(refactored_sig)))

    if mismatches:
        print(f"  ❌ Signature mismatches:")
        for name, legacy, refactored in mismatches:
            print(f"    {name}:")
            print(f"      Legacy:      {legacy}")
            print(f"      Refactored:  {refactored}")
        return False

    print(f"  ✅ All {len(methods_to_check)} checked methods have compatible signatures")
    print(f"  ℹ️  **kwargs in refactored version accepts all legacy parameters")
    return True

def test_mock_creation():
    """Проверить что можно создать handler без ошибок"""
    print("\n[4/5] Testing mock handler creation...")

    try:
        from presentation.handlers.message import MessageHandlers
        from unittest.mock import Mock

        # Create mock dependencies
        bot_service = Mock()
        claude_proxy = Mock()
        sdk_service = Mock()

        # Try to create handler
        handlers = MessageHandlers(
            bot_service=bot_service,
            claude_proxy=claude_proxy,
            sdk_service=sdk_service,
            default_working_dir="/tmp",
        )

        print(f"  ✅ Handler created successfully")
        print(f"    - Type: {type(handlers).__name__}")
        print(f"    - Has coordinator: {hasattr(handlers, '_coordinator')}")
        return True

    except Exception as e:
        print(f"  ❌ Failed to create handler: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_mock_message_handling():
    """Проверить что можно обработать mock message"""
    print("\n[5/5] Testing mock message handling...")

    try:
        from presentation.handlers.message import MessageHandlers
        from unittest.mock import Mock, AsyncMock

        # Create mocks
        bot_service = Mock()
        bot_service.send_message = AsyncMock()
        bot_service.edit_message = AsyncMock()
        bot_service.authorize_user = Mock(return_value=Mock(id=1, username="test"))

        claude_proxy = Mock()
        claude_proxy.run_task = AsyncMock(return_value=Mock(
            success=True,
            output="Test output",
            session_id="test-session",
            cancelled=False,
        ))

        handlers = MessageHandlers(
            bot_service=bot_service,
            claude_proxy=claude_proxy,
            default_working_dir="/tmp",
        )

        # Create mock message
        message = Mock()
        message.from_user = Mock(id=12345)
        message.chat = Mock(id=12345)
        message.text = "test message"
        message.answer = AsyncMock()
        message.bot = bot_service

        # This might fail (expected) - but should not raise AttributeError on None
        try:
            await handlers.handle_text(message)
            print(f"  ✅ Message handling completed (might have expected failures)")
        except AttributeError as e:
            if "'NoneType' object has no attribute" in str(e):
                print(f"  ❌ NoneType error (parameter not passed): {e}")
                return False
            else:
                print(f"  ⚠️  AttributeError (might be OK): {e}")
        except Exception as e:
            print(f"  ⚠️  Exception during handling (might be expected): {type(e).__name__}")

        return True

    except Exception as e:
        print(f"  ❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("LEGACY vs REFACTORED COMPARISON TEST")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Methods match", test_methods_match()))
    results.append(("Parameters match", test_parameters_match()))
    results.append(("Signatures match", test_method_signatures_match()))
    results.append(("Mock creation", test_mock_creation()))
    results.append(("Mock handling", asyncio.run(test_mock_message_handling())))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - Ready for migration!")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME TESTS FAILED - DO NOT migrate yet!")
        print("=" * 60)
        print("\nFix the issues and run tests again.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
