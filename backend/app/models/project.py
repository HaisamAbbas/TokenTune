import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    langfuse_public_key: Mapped[str | None] = mapped_column(String, nullable=True)
    langfuse_secret_key: Mapped[str | None] = mapped_column(String, nullable=True)

    environments: Mapped[list["Environment"]] = relationship(back_populates="project")

    @property
    def langfuse_configured(self) -> bool:
        """Whether both Langfuse keys are set - exposed via ProjectRead so
        the settings page can show configuration status without ever
        serializing the actual secret value back out."""
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    project: Mapped["Project"] = relationship(back_populates="environments")
