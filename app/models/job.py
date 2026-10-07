"""
Job ORM Model.

Represents a bulk certificate generation request. Tracks the overall progress,
aggregate counts, and completion status.
"""
import enum
from datetime import datetime, date
from typing import List, TYPE_CHECKING
from sqlalchemy import Integer, String, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.certificate import Certificate


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=JobStatus.QUEUED.value,
        index=True
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Controlled border customization
    border_style: Mapped[str] = mapped_column(String(20), nullable=False, default="double")
    border_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#1E3A8A")
    border_width: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationship: 1 Job -> Many Certificates
    # cascade="all, delete-orphan" ensures certificates are deleted if the job is deleted
    certificates: Mapped[List["Certificate"]] = relationship(
        "Certificate",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    @property
    def pending_count(self) -> int:
        """Remaining certificates to process."""
        return max(0, self.total_count - (self.success_count + self.failure_count))

    @property
    def progress_percentage(self) -> float:
        """
        Progress percentage based on formula:
        (success_count + failure_count) / total_count * 100
        """
        if self.total_count == 0:
            return 0.0
        processed = self.success_count + self.failure_count
        return round((processed / self.total_count) * 100.0, 2)

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, event='{self.event_name}', status='{self.status}', progress={self.progress_percentage}%)>"
