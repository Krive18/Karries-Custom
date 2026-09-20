from app.repositories.developer_platform_repository import aggregate_ai_usage


def test_aggregate_ai_usage_returns_only_real_hourly_and_provider_metrics():
    rows = [
        {
            "create_time": 7_200,
            "status": "failed",
            "latency_ms": 1_800,
            "provider": "doubao",
        },
        {
            "create_time": 7_260,
            "status": "success",
            "latency_ms": 420,
            "provider": "deepseek",
        },
        {
            "create_time": 10_800,
            "status": "success",
            "latency_ms": 900,
            "provider": "deepseek",
        },
    ]

    result = aggregate_ai_usage(rows)

    assert result["calls_24h"] == 3
    assert result["failures_24h"] == 1
    assert result["failure_rate"] == 33.3
    assert result["p95_latency_ms"] == 1_800
    assert result["trend"] == [
        {
            "timestamp": 7_200,
            "calls": 2,
            "failures": 1,
            "success_rate": 50.0,
            "p95_latency_ms": 1_800,
        },
        {
            "timestamp": 10_800,
            "calls": 1,
            "failures": 0,
            "success_rate": 100.0,
            "p95_latency_ms": 900,
        },
    ]
    assert result["providers"] == {
        "deepseek": {
            "calls": 2,
            "failures": 0,
            "failure_rate": 0.0,
            "p95_latency_ms": 900,
        },
        "doubao": {
            "calls": 1,
            "failures": 1,
            "failure_rate": 100.0,
            "p95_latency_ms": 1_800,
        },
    }
