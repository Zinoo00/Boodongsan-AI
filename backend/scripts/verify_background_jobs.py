#!/usr/bin/env python3
"""
Background job system verification script.
백그라운드 작업 시스템 검증 스크립트
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_dependencies():
    """Check if all required dependencies are installed."""
    print("🔍 Checking dependencies...")

    try:
        import celery
        print(f"  ✅ Celery installed: {celery.__version__}")
    except ImportError:
        print("  ❌ Celery not installed")
        return False

    try:
        import redis
        print(f"  ✅ Redis client installed")
    except ImportError:
        print("  ❌ Redis client not installed")
        return False

    try:
        import flower
        print(f"  ✅ Flower installed")
    except ImportError:
        print("  ❌ Flower not installed")
        return False

    return True


def check_celery_config():
    """Check Celery configuration."""
    print("\n🔍 Checking Celery configuration...")

    try:
        from jobs.celery_app import celery_app
        print(f"  ✅ Celery app imported successfully")
        print(f"  ✅ Broker: {celery_app.conf.broker_url}")
        print(f"  ✅ Backend: {celery_app.conf.result_backend}")
        print(f"  ✅ Task routes: {celery_app.conf.task_routes}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to import Celery app: {e}")
        return False


def check_tasks():
    """Check if tasks are properly registered."""
    print("\n🔍 Checking registered tasks...")

    try:
        from jobs.celery_app import celery_app
        import jobs.tasks  # Explicitly import to ensure tasks are registered

        registered_tasks = list(celery_app.tasks.keys())
        print(f"  ✅ Total registered tasks: {len(registered_tasks)}")

        expected_tasks = [
            "jobs.tasks.load_data_task",
            "jobs.tasks.cleanup_old_jobs",
            "jobs.tasks.test_task",
        ]

        for task_name in expected_tasks:
            if task_name in registered_tasks:
                print(f"  ✅ {task_name}")
            else:
                print(f"  ❌ {task_name} not found")
                return False

        return True
    except Exception as e:
        print(f"  ❌ Failed to check tasks: {e}")
        return False


def check_checkpoint_service():
    """Check checkpoint service."""
    print("\n🔍 Checking checkpoint service...")

    try:
        from services.checkpoint_service import CheckpointService

        service = CheckpointService()
        print(f"  ✅ CheckpointService initialized")
        print(f"  ✅ Checkpoint directory: {service.checkpoint_dir}")

        # Test save/load
        test_data = {"test": "data", "count": 42}
        service.save_checkpoint("test_job", test_data)
        loaded = service.load_checkpoint("test_job")

        if loaded and loaded.get("test") == "data":
            print(f"  ✅ Save/load test passed")
            service.clear_checkpoint("test_job")
            print(f"  ✅ Clear test passed")
            return True
        else:
            print(f"  ❌ Save/load test failed")
            return False

    except Exception as e:
        print(f"  ❌ Failed to check checkpoint service: {e}")
        return False


def check_monitoring():
    """Check monitoring integration."""
    print("\n🔍 Checking monitoring integration...")

    try:
        from core.monitoring import CloudWatchMetrics, MetricsAggregator

        # Try to initialize (will warn if boto3 not available, but won't fail)
        metrics = CloudWatchMetrics()
        print(f"  ✅ CloudWatchMetrics initialized")
        print(f"  ✅ Enabled: {metrics._enabled}")

        if metrics._enabled:
            print(f"  ✅ Namespace: {metrics.namespace}")
            print(f"  ✅ Region: {metrics.region}")
        else:
            print(f"  ⚠️  CloudWatch disabled (boto3 not installed or AWS credentials not configured)")

        return True
    except Exception as e:
        print(f"  ❌ Failed to check monitoring: {e}")
        return False


def check_redis_connection():
    """Check Redis connection."""
    print("\n🔍 Checking Redis connection...")

    try:
        from core.config import settings
        import redis

        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        print(f"  ✅ Redis connected: {settings.REDIS_URL}")

        # Set and get test value
        r.set("test_key", "test_value")
        value = r.get("test_key")
        r.delete("test_key")

        if value == "test_value":
            print(f"  ✅ Redis read/write test passed")
            return True
        else:
            print(f"  ❌ Redis read/write test failed")
            return False

    except Exception as e:
        print(f"  ❌ Redis connection failed: {e}")
        print(f"  ℹ️  Make sure Redis is running: docker-compose up -d redis")
        return False


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Background Job System Verification")
    print("=" * 60)

    checks = [
        ("Dependencies", check_dependencies),
        ("Celery Config", check_celery_config),
        ("Tasks", check_tasks),
        ("Checkpoint Service", check_checkpoint_service),
        ("Monitoring", check_monitoring),
        ("Redis Connection", check_redis_connection),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {name}")

    print(f"\nTotal: {passed}/{total} checks passed")

    if passed == total:
        print("\n🎉 All checks passed! Background job system is ready.")
        print("\nNext steps:")
        print("1. Start Redis: docker-compose up -d redis")
        print("2. Start Celery worker: uv run celery -A jobs.celery_app worker --loglevel=info")
        print("3. Start backend: uv run uvicorn api.main:app --reload")
        print("4. Test job: curl -X POST http://localhost:8000/api/v1/admin/jobs/test -d '{\"duration\": 10}'")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
