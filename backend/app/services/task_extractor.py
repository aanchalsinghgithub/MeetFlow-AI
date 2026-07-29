import re

from pydantic import ValidationError

from app.models.enums import Priority, TaskStatus
from app.schemas.meeting import TranscriptTurn
from app.schemas.task import ExtractedTask, TaskCreate
from app.services.confidence import score_task
from app.services.domain_classifier import DomainClassifier
from app.services.mistral_service import MistralService
from app.services.owner_resolver import resolve_owner
from app.services.team_mapping import load_team_mapping

TASK_PATTERNS = [
    re.compile(r"\bI(?:'ll| will)\s+(?P<task>.+?)(?:\s+by\s+(?P<deadline>[^.]+))?$", re.I),
    re.compile(r"\b(?P<owner>[A-Z][a-zA-Z]+)\s+should\s+(?P<task>.+?)(?:\s+by\s+(?P<deadline>[^.]+))?$", re.I),
    re.compile(r"\bwe need\s+(?P<task>.+?)(?:\s+before\s+(?P<deadline>[^.]+))?$", re.I),
    re.compile(r"\bplease\s+(?P<task>.+?)(?:\s+by\s+(?P<deadline>[^.]+))?$", re.I),
]

# BUGFIX: Mistral sometimes answers "confidence" with a word ("high") or a
# 0-10/0-100 scale instead of the 0-1 float the schema requires. This isn't
# something a prompt tweak can fully guarantee against (LLM output is never
# 100% schema-compliant), so it's normalized in code instead.
_CONFIDENCE_WORDS = {
    "very high": 0.95, "high": 0.9,
    "medium-high": 0.8, "moderate": 0.7, "medium": 0.7,
    "medium-low": 0.6, "low": 0.5, "very low": 0.3,
}

# Same idea for priority - map near-miss words to the enum's real values
# instead of failing validation outright.
_PRIORITY_ALIASES = {
    "critical": "urgent", "blocker": "urgent", "asap": "urgent",
    "important": "high", "normal": "medium", "default": "medium",
    "minor": "low", "trivial": "low",
}


class TaskExtractor:
    def __init__(self) -> None:
        self.classifier = DomainClassifier()
        self.mistral = MistralService()

    async def extract(self, transcript: list[TranscriptTurn]) -> list[TaskCreate]:
        tasks = self._rule_based_extract(transcript)
        if not tasks:
            tasks = await self._llm_extract(transcript)
        return [self._to_create(task) for task in tasks]

    def _rule_based_extract(self, transcript: list[TranscriptTurn]) -> list[ExtractedTask]:
        extracted: list[ExtractedTask] = []
        for turn in transcript:
            sentences = [part.strip() for part in re.split(r"[.\n]", turn.text) if part.strip()]
            for sentence in sentences:
                for pattern in TASK_PATTERNS:
                    match = pattern.search(sentence)
                    if not match:
                        continue
                    groups = match.groupdict()
                    task_text = self._clean_task(groups.get("task") or sentence)
                    owner = groups.get("owner") or (turn.speaker if sentence.lower().startswith(("i'll", "i will")) else None)
                    # BUGFIX: this used to pass whatever name (or "Unknown"
                    # diarization label) was found straight through as the
                    # owner. Now it's corrected against the team roster in
                    # team_mapping.json's "_people" block, and "Unknown"/
                    # empty values become None instead of a literal string
                    # that then gets emailed/displayed as someone's name.
                    owner = resolve_owner(owner)
                    domain = self.classifier.classify(task_text)
                    task = ExtractedTask(
                        task=task_text,
                        description=self._build_rule_description(
                            task_text, turn.speaker, sentence, groups.get("deadline")
                        ),
                        owner=owner,
                        mentioned_by=turn.speaker,
                        requested_by=self._requested_by(turn.speaker),
                        priority=self._priority(sentence),
                        deadline=groups.get("deadline"),
                        domain=domain.domain,
                    )
                    task.confidence = score_task(task, domain.confidence)
                    extracted.append(task)
                    break
        return extracted

    async def _llm_extract(self, transcript: list[TranscriptTurn]) -> list[ExtractedTask]:
        rendered = "\n".join(f"{turn.speaker}: {turn.text}" for turn in transcript)

        # BUGFIX: giving the model the real team roster fixes a lot of name
        # errors at the source, e.g. "Aacha"/"Archer" -> "Aanchal", instead
        # of relying on resolve_owner() to fuzzy-match after the fact.
        roster = load_team_mapping().get("_people", {}).get("members", [])
        roster_hint = ""
        if roster:
            roster_hint = (
                "This transcript comes from speech-to-text and names are "
                f"sometimes misheard. The real team members are: {', '.join(roster)}. "
                "If a name in the transcript sounds like a mis-transcription of one "
                "of these, use the correct spelling from this list as the owner.\n\n"
            )

        prompt = (
            "Extract meeting tasks as JSON array with keys task, description, owner, "
            "mentioned_by, requested_by, priority, deadline, dependencies, confidence. "
            "task: a short imperative title (e.g. 'Fix API timeout issue'). "
            "description: 2-4 full sentences, written for someone who was NOT in the "
            "meeting, that clearly explain what needs to be done, why it came up in the "
            "discussion, and any context, constraints, or specifics mentioned (e.g. which "
            "system/feature it affects, what triggered it). Do not just restate the task "
            "title - describe it the way you'd explain it to a teammate who missed the call. "
            "priority must be exactly one of: low, medium, high, urgent. "
            "confidence must be a number between 0 and 1 (e.g. 0.8) — not a word like "
            "'high' and not a 0-10 or percentage scale. "
            "Set owner to null if no specific person is mentioned for that task — "
            "never invent a name and never use the word 'Unknown'.\n\n"
            f"{roster_hint}{rendered}"
        )
        records = await self.mistral.extract_json(prompt)
        print(f"[TaskExtractor] Mistral returned {len(records)} record(s): {records}")
        tasks: list[ExtractedTask] = []
        for record in records:
            # BUGFIX: the model was asked for (and returned) a "domain" key
            # too, but it filled it with things like the project name
            # ("NetFlow AI") rather than a routable category — which
            # silently broke the frontend/backend/aws email-routing rules
            # in team_mapping.json, since "NetFlow AI" matches no domain
            # there and always fell back to the default manager email.
            # Domain is now always decided by the deterministic keyword
            # classifier below instead of trusting the LLM's guess.
            record.pop("domain", None)
            # BUGFIX: previously only lower-cased priority if it was already
            # a valid-looking string, and left confidence completely
            # untouched. A record like {"confidence": "high"} would then
            # fail Pydantic validation and get dropped ENTIRELY — including
            # a correctly-extracted task/owner — instead of just that one
            # field being wrong. Both are now normalized up front.
            record["priority"] = self._coerce_priority(record.get("priority"))
            record["confidence"] = self._coerce_confidence(record.get("confidence"))
            if "owner" in record:
                record["owner"] = resolve_owner(record.get("owner"))
            try:
                task = ExtractedTask(**record)
            except ValidationError as e:
                # Last resort: strip out whichever specific field(s) are
                # still invalid (everything except `task` itself has a safe
                # schema default) and retry once, rather than losing the
                # whole task over one bad field.
                task = self._salvage_task(record, e)
                if task is None:
                    print("[TaskExtractor] Skipping unsalvageable record:", record, "error:", e)
                    continue
                print("[TaskExtractor] Salvaged record by clearing invalid field(s):", record)
            task.domain = self.classifier.classify(task.task).domain
            tasks.append(task)
        return tasks

    @staticmethod
    def _salvage_task(record: dict, error: ValidationError) -> ExtractedTask | None:
        cleaned = dict(record)
        for err in error.errors():
            field = err["loc"][0] if err.get("loc") else None
            if field and field in cleaned:
                cleaned.pop(field)  # drop it - the schema default takes over
        try:
            return ExtractedTask(**cleaned)
        except Exception:
            return None

    @staticmethod
    def _coerce_confidence(value) -> float:
        if value is None:
            return 0.6
        if isinstance(value, bool):  # bool is a subclass of int - reject explicitly
            return 0.6
        if isinstance(value, (int, float)):
            v = float(value)
            if v > 1:
                v = v / 100 if v > 10 else v / 10  # handle 0-10 or 0-100 scales
            return max(0.0, min(v, 0.98))
        if isinstance(value, str):
            s = value.strip().lower()
            try:
                return TaskExtractor._coerce_confidence(float(s))
            except ValueError:
                pass
            if s in _CONFIDENCE_WORDS:
                return _CONFIDENCE_WORDS[s]
        return 0.6  # unrecognized shape - safe default instead of dropping the task

    @staticmethod
    def _coerce_priority(value) -> str:
        if isinstance(value, str):
            s = _PRIORITY_ALIASES.get(value.strip().lower(), value.strip().lower())
            if s in {p.value for p in Priority}:
                return s
        return Priority.MEDIUM.value

    def _to_create(self, task: ExtractedTask) -> TaskCreate:
        status = (
            TaskStatus.AUTO_APPROVE_CANDIDATE
            if task.confidence > 0.9
            else TaskStatus.REVIEW_REQUIRED
        )
        return TaskCreate(
            title=task.task,
            # BUGFIX: this used to be `description=task.task`, i.e. every task's
            # "description" was a byte-for-byte copy of its title. That's what
            # made the "Task Assigned" email show an identical Task Name and
            # Task Description (email_service.py::task_assignment falls back
            # to task.title only when description is empty - it was never
            # empty, it was just a duplicate). Now the description carries
            # actual context: the LLM path returns a real explanation (see the
            # prompt above), and the rule-based path quotes the transcript
            # line it came from. _fallback_description only fires if both of
            # those still come back empty.
            description=task.description or self._fallback_description(task),
            owner=task.owner,
            mentioned_by=task.mentioned_by,
            requested_by=task.requested_by,
            priority=task.priority,
            deadline=task.deadline,
            domain=task.domain,
            dependencies=task.dependencies,
            confidence=task.confidence,
            status=status,
        )

    @staticmethod
    def _build_rule_description(task_text: str, speaker: str, sentence: str, deadline: str | None) -> str:
        """Quote the actual transcript line a rule-matched task came from,
        instead of leaving description unset (which used to fall back to a
        copy of the title - see the BUGFIX note in _to_create)."""
        quoted = sentence.strip().strip(".")
        base = f'{speaker} said: "{quoted}." Action needed: {task_text}.'
        return f"{base} Deadline mentioned: {deadline}." if deadline else base

    @staticmethod
    def _fallback_description(task: "ExtractedTask") -> str:
        """Last-resort description when neither the LLM nor the rule-based
        path produced one - still adds who/when context instead of being a
        bare duplicate of the title."""
        parts = [f"{task.task}."]
        if task.mentioned_by:
            parts.append(f"Mentioned by {task.mentioned_by} during the meeting.")
        if task.requested_by and task.requested_by != task.mentioned_by:
            parts.append(f"Requested by {task.requested_by}.")
        if task.deadline:
            parts.append(f"Needed by {task.deadline}.")
        return " ".join(parts)

    @staticmethod
    def _clean_task(text: str) -> str:
        cleaned = text.strip(" .").replace("fixed", "fix")
        return cleaned[:1].upper() + cleaned[1:]

    @staticmethod
    def _requested_by(speaker: str) -> str:
        return "Client" if speaker.lower() in {"client", "customer"} else f"{speaker}"

    @staticmethod
    def _priority(sentence: str) -> Priority:
        lowered = sentence.lower()
        if any(word in lowered for word in ["urgent", "asap", "blocker"]):
            return Priority.URGENT
        if any(word in lowered for word in ["before", "demo", "critical"]):
            return Priority.HIGH
        return Priority.MEDIUM
