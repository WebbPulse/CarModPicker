"""A-01 regression: lifespan orphan sweeps must run inside bg_log_context
so log lines emitted by sweep_orphan_schedules / sweep_orphan_jobs carry
request_id="bg:orphan-schedule-sweep:-" / "bg:orphan-jobs-sweep:-" rather
than the default "-".

See .planning/v1.0-INTEGRATION-CHECK.md §Advisory A-01.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.log_context import request_id_var, user_id_var


@pytest.mark.asyncio
async def test_orphan_schedule_sweep_runs_under_bg_log_context() -> None:
    """During crawler_schedule_service.sweep_orphan_schedules, the
    request_id ContextVar should be 'bg:orphan-schedule-sweep:-'.
    """
    from app import main as main_module

    captured_request_ids: list[str] = []

    def fake_sweep_orphan_schedules(db: object) -> list[object]:
        # Capture the request_id at the exact moment the sweep runs.
        captured_request_ids.append(request_id_var.get())
        return []

    def fake_sweep_orphan_jobs(db: object, current_worker_instance_id: object = None) -> list[object]:
        return []

    with patch.object(
        main_module.crawler_schedule_service,
        "sweep_orphan_schedules",
        side_effect=fake_sweep_orphan_schedules,
    ), patch.object(
        main_module.job_service,
        "sweep_orphan_jobs",
        side_effect=fake_sweep_orphan_jobs,
    ), patch.object(
        main_module, "init_crawler_service_account", return_value=None
    ), patch.object(
        main_module, "init_crawler_adapter_configs", return_value=None
    ), patch.object(
        main_module, "init_car_generations", return_value=None
    ), patch("app.main.SessionLocal", return_value=MagicMock()):
        async with main_module.lifespan(MagicMock()):
            pass

    assert captured_request_ids == ["bg:orphan-schedule-sweep:-"], (
        f"Expected sweep_orphan_schedules to run with "
        f"request_id='bg:orphan-schedule-sweep:-', got {captured_request_ids}"
    )


@pytest.mark.asyncio
async def test_orphan_jobs_sweep_runs_under_bg_log_context() -> None:
    """During job_service.sweep_orphan_jobs, the request_id ContextVar
    should be 'bg:orphan-jobs-sweep:-'.
    """
    from app import main as main_module

    captured_request_ids: list[str] = []

    def fake_sweep_orphan_schedules(db: object) -> list[object]:
        return []

    def fake_sweep_orphan_jobs(db: object, current_worker_instance_id: object = None) -> list[object]:
        captured_request_ids.append(request_id_var.get())
        return []

    with patch.object(
        main_module.crawler_schedule_service,
        "sweep_orphan_schedules",
        side_effect=fake_sweep_orphan_schedules,
    ), patch.object(
        main_module.job_service,
        "sweep_orphan_jobs",
        side_effect=fake_sweep_orphan_jobs,
    ), patch.object(
        main_module, "init_crawler_service_account", return_value=None
    ), patch.object(
        main_module, "init_crawler_adapter_configs", return_value=None
    ), patch.object(
        main_module, "init_car_generations", return_value=None
    ), patch("app.main.SessionLocal", return_value=MagicMock()):
        async with main_module.lifespan(MagicMock()):
            pass

    assert captured_request_ids == ["bg:orphan-jobs-sweep:-"], (
        f"Expected sweep_orphan_jobs to run with "
        f"request_id='bg:orphan-jobs-sweep:-', got {captured_request_ids}"
    )


@pytest.mark.asyncio
async def test_request_id_is_reset_after_lifespan_exits() -> None:
    """After lifespan context exits, request_id_var should return to its
    default '-' (bg_log_context uses re-entrant-safe token reset).
    """
    from app import main as main_module

    with patch.object(
        main_module.crawler_schedule_service,
        "sweep_orphan_schedules",
        return_value=[],
    ), patch.object(
        main_module.job_service, "sweep_orphan_jobs", return_value=[]
    ), patch.object(
        main_module, "init_crawler_service_account", return_value=None
    ), patch.object(
        main_module, "init_crawler_adapter_configs", return_value=None
    ), patch.object(
        main_module, "init_car_generations", return_value=None
    ), patch("app.main.SessionLocal", return_value=MagicMock()):
        async with main_module.lifespan(MagicMock()):
            pass

    assert request_id_var.get() == "-", (
        f"request_id_var should reset to '-' after lifespan, got {request_id_var.get()!r}"
    )
    assert user_id_var.get() == "-", (
        f"user_id_var should reset to '-' after lifespan, got {user_id_var.get()!r}"
    )
