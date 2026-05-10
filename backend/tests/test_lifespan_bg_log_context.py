"""A-01 regression: lifespan orphan sweeps must run inside bg_log_context
so log lines emitted by sweep_orphan_jobs carry
request_id="bg:orphan-jobs-sweep:-" rather than the default "-".
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.log_context import request_id_var, user_id_var


@pytest.mark.asyncio
async def test_orphan_jobs_sweep_runs_under_bg_log_context() -> None:
    """During job_service.sweep_orphan_jobs, the request_id ContextVar
    should be 'bg:orphan-jobs-sweep:-' and user_id should be 'bg'.
    """
    from app import main as main_module

    captured: list[tuple[str, str]] = []

    def fake_sweep_orphan_jobs(db: object, current_worker_instance_id: object = None) -> list[object]:
        captured.append((request_id_var.get(), user_id_var.get()))
        return []

    with (
        patch.object(main_module.job_service, "sweep_orphan_jobs", side_effect=fake_sweep_orphan_jobs),
        patch.object(main_module, "init_car_generations", return_value=None),
        patch("app.main.SessionLocal", return_value=MagicMock()),
    ):
        async with main_module.lifespan(MagicMock()):
            pass

    assert captured == [("bg:orphan-jobs-sweep:-", "bg")], (
        f"Expected sweep_orphan_jobs to run with "
        f"(request_id, user_id)=('bg:orphan-jobs-sweep:-', 'bg'), "
        f"got {captured}"
    )


@pytest.mark.asyncio
async def test_request_id_is_reset_after_lifespan_exits() -> None:
    """After lifespan context exits, request_id_var should return to its default '-'."""
    from app import main as main_module

    with (
        patch.object(main_module.job_service, "sweep_orphan_jobs", return_value=[]),
        patch.object(main_module, "init_car_generations", return_value=None),
        patch("app.main.SessionLocal", return_value=MagicMock()),
    ):
        async with main_module.lifespan(MagicMock()):
            pass

    assert (
        request_id_var.get() == "-"
    ), f"request_id_var should reset to '-' after lifespan, got {request_id_var.get()!r}"
    assert user_id_var.get() == "-", f"user_id_var should reset to '-' after lifespan, got {user_id_var.get()!r}"
