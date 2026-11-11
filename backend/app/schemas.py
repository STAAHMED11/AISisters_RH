from typing import Literal

from pydantic import BaseModel


class CriterionIn(BaseModel):
    label: str
    description: str = ""
    kind: Literal["must", "nice"] = "must"
    source: Literal["cv", "interview"] = "cv"


class CriterionEdit(CriterionIn):
    id: int = 0


class CriteriaExtraction(BaseModel):
    title: str
    ref: str = ""
    criteria: list[CriterionIn]


class JobIn(BaseModel):
    description: str
    title: str = ""
    ref: str = ""


class LangLevel(BaseModel):
    lang: str
    level: str


class Profile(BaseModel):
    is_cv: bool
    name: str
    email: str
    phone: str
    city: str
    current_title: str
    years_experience: float
    education_level: str
    education: list[str]
    languages: list[LangLevel]
    skills: list[str]
    certifications: list[str]
    cv_language: str
    headline: str


class Transcription(BaseModel):
    text: str


class InjectionScan(BaseModel):
    injected: bool
    evidence: list[str]


class CritEval(BaseModel):
    criterion_id: int
    verdict: Literal["met", "partial", "not_met", "not_evidenced"]
    quote: str
    rationale: str


class CVEvaluation(BaseModel):
    evaluations: list[CritEval]
    summary: str


class PlanQuestion(BaseModel):
    criterion_id: int
    kind: Literal["logistics", "verify", "probe", "closing"]
    question: str
    listen_for: str


class InterviewPlan(BaseModel):
    questions: list[PlanQuestion]


class Grade(BaseModel):
    criterion_id: int
    grade: int
    quote: str
    rationale: str


class Evidence(BaseModel):
    text: str
    quote: str


class Logistic(BaseModel):
    label: str
    answer: str


class Synthesis(BaseModel):
    grades: list[Grade]
    strengths: list[Evidence]
    doubts: list[Evidence]
    probes: list[str]
    logistics: list[Logistic]
    blockers: list[str]
    discrepancies: list[str]
    recommendation: Literal["invite", "hold", "decline"]
    headline: str
    manipulation: bool


class Draft(BaseModel):
    subject: str
    body: str
