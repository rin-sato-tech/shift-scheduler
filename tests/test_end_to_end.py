from __future__ import annotations

from datetime import date

from src.day_off_service import (
    register_day_off_request,
)
from src.employee_service import (
    register_employee,
)
from src.models import StaffingRequirement
from src.repositories import (
    list_schedule_assignments,
)
from src.schedule_service import (
    generate_month_schedule,
)
from src.staffing_service import (
    save_month_staffing_requirements,
)
from src.export_service import (
    dataframe_to_csv_bytes,
    get_schedule_export_data,
)


def test_full_schedule_workflow(
    initialized_test_db,
) -> None:
    for employee_id, name, is_manager in [
        ("E001", "山田", True),
        ("E002", "佐藤", True),
        ("E003", "鈴木", False),
        ("E004", "高橋", False),
    ]:
        result = register_employee(
            employee_id=employee_id,
            name=name,
            is_manager=is_manager,
            contract_days=16,
            can_work_early=True,
            can_work_late=True,
        )

        assert result.succeeded is True

    day_off_result = register_day_off_request(
        employee_id="E001",
        target_date=date(2026, 8, 5),
        target_month="2026-08",
    )

    assert day_off_result.succeeded is True

    requirements = [
        StaffingRequirement(
            target_date=date(
                2026,
                8,
                day,
            ),
            shift_type=shift_type,
            required_count=1,
            required_manager_count=0,
        )
        for day in range(1, 32)
        for shift_type in (
            "early",
            "late",
        )
    ]

    staffing_result = (
        save_month_staffing_requirements(
            target_month="2026-08",
            requirements=requirements,
        )
    )

    assert staffing_result.succeeded is True

    generation_result = (
        generate_month_schedule(
            "2026-08",
            max_time_seconds=5,
            num_search_workers=1,
        )
    )

    assert generation_result.generated is True

    assignments = list_schedule_assignments(
        "2026-08"
    )

    assert len(assignments) == 62

    assert not any(
        assignment.employee_id == "E001"
        and assignment.target_date
        == date(2026, 8, 5)
        for assignment in assignments
    )

    export_data = get_schedule_export_data(
        "2026-08"
    )

    assert len(
        export_data.assignment_detail
    ) == 62

    detail_csv = dataframe_to_csv_bytes(
        export_data.assignment_detail
    )

    assert detail_csv.startswith(
        b"\xef\xbb\xbf"
    )

    decoded_csv = detail_csv.decode(
        "utf-8-sig"
    )

    assert "従業員ID" in decoded_csv
    assert "氏名" in decoded_csv
    assert "シフト" in decoded_csv

    detail_df = (
        export_data.assignment_detail
    )

    e001_day_off_rows = detail_df[
        (
            detail_df["従業員ID"]
            == "E001"
        )
        & (
            detail_df["日付"]
            == "2026/08/05"
        )
    ]

    assert e001_day_off_rows.empty