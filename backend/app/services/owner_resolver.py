"""Last-line-of-defense cleanup for owner names, AFTER transcription.

You correctly pointed out the limit of this file: we can't know in advance
every wrong word Whisper will produce, so a hand-maintained alias list
("aacha" -> "Aanchal") only ever covers mistakes you've already seen. It
is not, and can't be, a complete fix.

The real fix lives upstream, in transcription_service.py: every chunk's
Whisper call is now primed with your team roster via `initial_prompt`,
which biases what the model hears in the first place — a name it's been
told to expect gets transcribed correctly far more often than one it has
to guess cold. That prevents mishears instead of reacting to them.

This file is what's left after that: a cheap, best-effort cleanup for
whatever still slips through -

    "_people": {
        "members": ["Aanchal", "Rohit", "Seema"],
        "aliases": {"aacha": "Aanchal"}   # optional - only add entries you
                                           # actually keep seeing repeat
    }

- exact/fuzzy matching here will catch close spelling variants, but it
  will NOT catch every mishear (e.g. a name that sounds nothing like its
  correct spelling once garbled). When it can't find a confident match it
  deliberately leaves the raw text alone rather than guessing — the
  actual safety net for those cases is a human: the Edit button in the
  Approvals screen lets you fix the owner by hand in a few seconds, which
  is always going to be more reliable than any string-matching heuristic.
"""

import difflib

from app.services.team_mapping import load_team_mapping

_UNKNOWN_VALUES = {"", "unknown", "n/a", "none", "null", "tbd"}


def resolve_owner(raw_name: str | None) -> str | None:
    if not raw_name or raw_name.strip().lower() in _UNKNOWN_VALUES:
        return None

    people = load_team_mapping().get("_people", {})
    members: list[str] = people.get("members", [])
    aliases: dict[str, str] = {k.lower(): v for k, v in people.get("aliases", {}).items()}

    name = raw_name.strip()
    lowered = name.lower()

    # 1. Explicit alias for a mistake you've specifically told us about.
    if lowered in aliases:
        return aliases[lowered]

    # 2. Exact roster match, case-insensitive.
    for member in members:
        if member.lower() == lowered:
            return member

    # 3. Fuzzy match — catches close spelling variants (e.g. "Rohith" for
    #    "Rohit"). This is a spelling-similarity check, not a phonetic
    #    one, so it will miss mishears that sound alike but are spelled
    #    very differently ("Archer" vs "Aanchal" won't match here — that
    #    kind of miss is exactly why the initial_prompt fix upstream and
    #    the Approvals Edit button matter more than this function does).
    pool = {m.lower(): m for m in members}
    pool.update(aliases)
    close = difflib.get_close_matches(lowered, pool.keys(), n=1, cutoff=0.55)
    if close:
        return pool[close[0]]

    # No confident match — keep the raw name (instead of returning None)
    # so a human reviewer can still see and fix it in the approval queue,
    # rather than silently losing the information.
    return name
