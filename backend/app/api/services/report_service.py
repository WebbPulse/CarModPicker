"""
Unified report service for all entity types.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Type, Union
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.part import Part as DBPart
from app.api.models.report import Report as DBReport
from app.api.models.user import User as DBUser
from app.api.schemas.report import (
    EntityType,
    ReportCreate,
    ReportRead,
    ReportWithDetails,
)
from app.api.utils.common_operations import verify_entity_exists


class ReportService:
    """
    Unified report service for all entity types.

    This service handles reporting operations for build lists and global parts
    using the unified Report model.
    """

    def __init__(self) -> None:
        """Initialize the unified report service."""
        pass

    def create_report(
        self,
        db: Session,
        entity_type: EntityType,
        entity_id: UUID,
        user_id: UUID,
        report_data: ReportCreate,
        logger: logging.Logger,
    ) -> DBReport:
        """
        Create a report for an entity.

        Args:
            db: Database session
            entity_type: Type of entity being reported
            entity_id: ID of the entity
            user_id: ID of the user reporting
            report_data: Report data
            logger: Logger instance

        Returns:
            The created report

        Raises:
            HTTPException: If entity doesn't exist or user tries to report their own entity
        """
        # Verify entity exists
        entity_model = self._get_entity_model(entity_type)
        entity = verify_entity_exists(db, entity_model, entity_id, entity_type.value)

        # Check if user is trying to report their own entity
        if entity.user_id == user_id:
            raise HTTPException(
                status_code=400,
                detail=f"You cannot report your own {entity_type.value}",
            )

        # Check if user has already reported this entity with a pending report
        existing_report = db.scalars(
            select(DBReport).where(
                DBReport.user_id == user_id,
                DBReport.entity_type == entity_type.value,
                DBReport.entity_id == entity_id,
                DBReport.status == "pending",
            )
        ).first()

        if existing_report:
            raise HTTPException(status_code=400, detail="You have already reported this entity")

        # Create new report
        db_report = DBReport(
            user_id=user_id,
            entity_type=entity_type.value,
            entity_id=entity_id,
            reason=report_data.reason.value,
            description=report_data.description,
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)

        logger.info(f"Report created: {db_report.id} by user {user_id} on {entity_type.value} {entity_id}")
        return db_report

    def get_reports(
        self,
        db: Session,
        entity_type: Optional[EntityType] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[ReportRead]:
        """
        Get reports with optional filtering.

        Args:
            db: Database session
            entity_type: Optional entity type filter
            status: Optional status filter
            skip: Number of reports to skip
            limit: Maximum number of reports to return
            logger: Optional logger instance

        Returns:
            List of reports
        """
        stmt = select(DBReport)

        if entity_type:
            stmt = stmt.where(DBReport.entity_type == entity_type.value)

        if status:
            stmt = stmt.where(DBReport.status == status)

        reports = db.scalars(
            stmt.order_by(desc(DBReport.created_at)).offset(skip).limit(limit)
        ).all()

        return [ReportRead.model_validate(report) for report in reports]

    def get_reports_with_details(
        self,
        db: Session,
        entity_type: Optional[EntityType] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> tuple[List[ReportWithDetails], int]:
        """
        Get reports with detailed information including reporter and entity details.

        Args:
            db: Database session
            entity_type: Optional entity type filter
            status: Optional status filter
            skip: Number of reports to skip
            limit: Maximum number of reports to return
            logger: Optional logger instance

        Returns:
            Tuple of (list of reports with details, total count)
        """
        base_stmt = select(
            DBReport,
            DBUser.username.label("reporter_username"),
            DBUser.id.label("reporter_id"),
        ).join(DBUser, DBReport.user_id == DBUser.id)

        if entity_type:
            base_stmt = base_stmt.where(DBReport.entity_type == entity_type.value)

        if status:
            base_stmt = base_stmt.where(DBReport.status == status)

        # Get total count before pagination
        total_count = db.scalar(
            select(func.count()).select_from(base_stmt.subquery())
        ) or 0

        # Get entity details based on type
        entity_details: List[ReportWithDetails] = []
        for report, reporter_username, _ in db.execute(
            base_stmt.order_by(desc(DBReport.created_at)).offset(skip).limit(limit)
        ).all():
            entity = self._get_entity_details(db, report.entity_type, report.entity_id)

            # Get reviewer username if reviewed
            reviewer_username = None
            if report.reviewed_by:
                reviewer = db.scalars(
                    select(DBUser).where(DBUser.id == report.reviewed_by)
                ).first()
                reviewer_username = reviewer.username if reviewer else None

            entity_details.append(
                ReportWithDetails(
                    id=report.id,
                    user_id=report.user_id,
                    entity_type=report.entity_type,
                    entity_id=report.entity_id,
                    reason=report.reason,
                    description=report.description,
                    status=report.status,
                    admin_notes=report.admin_notes,
                    reviewed_by=report.reviewed_by,
                    reviewed_at=report.reviewed_at,
                    created_at=report.created_at,
                    updated_at=report.updated_at,
                    reporter_username=reporter_username,
                    entity_name=entity["name"],
                    entity_description=entity.get("description"),
                    reviewer_username=reviewer_username,
                )
            )

        return entity_details, total_count

    def update_report(
        self,
        db: Session,
        report_id: UUID,
        status: str,
        admin_notes: Optional[str] = None,
        reviewer_id: Optional[UUID] = None,
        logger: Optional[logging.Logger] = None,
    ) -> DBReport:
        """
        Update a report (typically for admin review).

        Args:
            db: Database session
            report_id: ID of the report to update
            status: New status for the report
            admin_notes: Optional admin notes
            reviewer_id: Optional reviewer ID
            logger: Optional logger instance

        Returns:
            The updated report

        Raises:
            HTTPException: If report doesn't exist
        """
        report = db.scalars(select(DBReport).where(DBReport.id == report_id)).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        report.status = status
        report.admin_notes = admin_notes
        report.reviewed_by = reviewer_id
        report.reviewed_at = datetime.now(UTC)
        report.updated_at = datetime.now(UTC)

        db.commit()
        db.refresh(report)

        if logger:
            logger.info(f"Report updated: {report_id} by reviewer {reviewer_id} to status {status}")

        return report

    def delete_report(
        self,
        db: Session,
        report_id: UUID,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Delete a report (admin only).

        Args:
            db: Database session
            report_id: ID of the report to delete
            logger: Optional logger instance

        Raises:
            HTTPException: If report doesn't exist
        """
        report = db.scalars(select(DBReport).where(DBReport.id == report_id)).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        db.delete(report)
        db.commit()

        if logger:
            logger.info(f"Report deleted: {report_id}")

    def get_user_reports(
        self,
        db: Session,
        user_id: UUID,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[ReportRead]:
        """
        Get all reports created by a specific user.

        Args:
            db: Database session
            user_id: ID of the user
            status: Optional status filter
            skip: Number of reports to skip
            limit: Maximum number of reports to return
            logger: Optional logger instance

        Returns:
            List of reports created by the user
        """
        stmt = select(DBReport).where(DBReport.user_id == user_id)

        if status:
            stmt = stmt.where(DBReport.status == status)

        reports = db.scalars(
            stmt.order_by(desc(DBReport.created_at)).offset(skip).limit(limit)
        ).all()

        if logger:
            logger.info(f"Retrieved {len(reports)} reports by user {user_id}")

        return [ReportRead.model_validate(report) for report in reports]

    def get_report_by_id(
        self,
        db: Session,
        report_id: UUID,
        current_user_id: UUID,
        is_admin: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> Optional[ReportWithDetails]:
        """
        Get a specific report by ID with authorization check.

        Args:
            db: Database session
            report_id: ID of the report to retrieve
            current_user_id: ID of the current user
            is_admin: Whether the current user is an admin
            logger: Optional logger instance

        Returns:
            Report with details if found and authorized, None otherwise
        """
        # Query the report with user details
        result = db.execute(
            select(
                DBReport,
                DBUser.username.label("reporter_username"),
                DBUser.id.label("reporter_id"),
            )
            .join(DBUser, DBReport.user_id == DBUser.id)
            .where(DBReport.id == report_id)
        ).first()

        if not result:
            return None

        report, reporter_username, _ = result

        # Authorization check: user can only see their own reports unless they're admin
        if not is_admin and report.user_id != current_user_id:
            return None

        # Get entity details
        entity = self._get_entity_details(db, report.entity_type, report.entity_id)

        # Get reviewer username if reviewed
        reviewer_username = None
        if report.reviewed_by:
            reviewer = db.scalars(
                select(DBUser).where(DBUser.id == report.reviewed_by)
            ).first()
            reviewer_username = reviewer.username if reviewer else None

        return ReportWithDetails(
            id=report.id,
            user_id=report.user_id,
            entity_type=report.entity_type,
            entity_id=report.entity_id,
            reason=report.reason,
            description=report.description,
            status=report.status,
            admin_notes=report.admin_notes,
            reviewed_by=report.reviewed_by,
            reviewed_at=report.reviewed_at,
            created_at=report.created_at,
            updated_at=report.updated_at,
            reporter_username=reporter_username,
            entity_name=entity["name"],
            entity_description=entity.get("description"),
            reviewer_username=reviewer_username,
        )

    def _get_entity_model(self, entity_type: EntityType) -> Type[Union[DBBuildList, DBPart]]:
        """Get the SQLAlchemy model for the entity type."""
        if entity_type == EntityType.BUILD_LIST:
            return DBBuildList
        elif entity_type == EntityType.PART:
            return DBPart
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def _get_entity_details(self, db: Session, entity_type: str, entity_id: UUID) -> Dict[str, Any]:
        """Get entity details for report display."""
        if entity_type == "build_list":
            bl = db.scalars(select(DBBuildList).where(DBBuildList.id == entity_id)).first()
            if bl:
                return {"name": bl.name, "description": bl.description}
        elif entity_type == "part":
            part = db.scalars(select(DBPart).where(DBPart.id == entity_id)).first()
            if part:
                return {"name": part.name, "description": part.description}

        return {"name": f"Unknown {entity_type}", "description": None}
