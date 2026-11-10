from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    ref: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=now)
    criteria_updated_at: Mapped[datetime] = mapped_column(default=now)
    criteria: Mapped[list["Criterion"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Criterion.position"
    )
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Criterion(Base):
    __tablename__ = "criteria"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(10), default="must")  # must | nice
    source: Mapped[str] = mapped_column(String(10), default="cv")  # cv | interview
    position: Mapped[int] = mapped_column(Integer, default=0)
    job: Mapped[Job] = relationship(back_populates="criteria")


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(300), default="")
    mime: Mapped[str] = mapped_column(String(100), default="")
    file_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="uploaded")
    error: Mapped[str] = mapped_column(Text, default="")

    text_raw: Mapped[str] = mapped_column(Text, default="")
    text_anon: Mapped[str] = mapped_column(Text, default="")
    hidden_text: Mapped[list] = mapped_column(JSON, default=list)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    lang: Mapped[str] = mapped_column(String(10), default="")

    injection_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    injection_evidence: Mapped[list] = mapped_column(JSON, default=list)

    cv_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    triage: Mapped[str] = mapped_column(String(10), default="")  # yes | maybe | no
    prequal: Mapped[str] = mapped_column(String(10), default="")  # pass | review | fail
    summary: Mapped[str] = mapped_column(Text, default="")

    token: Mapped[str] = mapped_column(String(80), default="", index=True)
    interview_note: Mapped[float | None] = mapped_column(Float, nullable=True)
    global_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    decision: Mapped[str] = mapped_column(String(20), default="")  # accepted | rejected
    created_at: Mapped[datetime] = mapped_column(default=now)
    screened_at: Mapped[datetime | None] = mapped_column(nullable=True)

    job: Mapped[Job] = relationship(back_populates="candidates")
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    interview: Mapped["Interview | None"] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", uselist=False
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", order_by="Decision.id"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", order_by="Message.id"
    )


class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    criterion_id: Mapped[int] = mapped_column(ForeignKey("criteria.id", ondelete="CASCADE"))
    verdict: Mapped[str] = mapped_column(String(20))  # met|partial|not_met|not_evidenced
    quote: Mapped[str] = mapped_column(Text, default="")
    quote_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    candidate: Mapped[Candidate] = relationship(back_populates="evaluations")


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), unique=True)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    language: Mapped[str] = mapped_column(String(10), default="fr")
    mode: Mapped[str] = mapped_column(String(10), default="")  # voice | text
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|started|ended|scored
    consent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    el_conversation_id: Mapped[str] = mapped_column(String(100), default="")
    transcript: Mapped[list] = mapped_column(JSON, default=list)  # [{role, text}]
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    synthesis: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=now)
    candidate: Mapped[Candidate] = relationship(back_populates="interview")


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    actor: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(20))  # accept | reject | override
    ai_proposed: Mapped[str] = mapped_column(String(20), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=now)
    candidate: Mapped[Candidate] = relationship(back_populates="decisions")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # invite | rejection | acceptance | hold
    language: Mapped[str] = mapped_column(String(10), default="fr")
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|sent
    created_at: Mapped[datetime] = mapped_column(default=now)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    transport: Mapped[str] = mapped_column(String(10), default="")  # smtp | mock
    candidate: Mapped[Candidate] = relationship(back_populates="messages")


class UsageEvent(Base):
    """One billable event: an LLM call (tokens) or an ElevenLabs voice call (minutes). Source of truth for the cost dashboard."""
    __tablename__ = "usage_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(default=now)
    provider: Mapped[str] = mapped_column(String(20))  # anthropic | elevenlabs
    model: Mapped[str] = mapped_column(String(80), default="")
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    job_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    candidate_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    ref: Mapped[str] = mapped_column(String(100), default="")  # e.g. ElevenLabs conversation id (dedupe)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(default=now)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(50), default="")
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
