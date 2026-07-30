"""The block you paste into another agent's brief.

Spinning a stream up used to be three commands and a hand-written paragraph, and
the paragraph was the part that went wrong: an agent that had never seen this
bridge had to be told, in prose, how to listen and when it was allowed to stop.
Get that last part wrong and the agent finishes its task and vanishes, which is
the failure this whole project exists to fix.

So the wording lives here, in one place, and ``argybargy room`` prints it. It is
plain HTTP and plain English on purpose: it has to work verbatim for a Codex
session, a Gemini session, another vendor entirely, or a person with a terminal.
Nothing in it is specific to any model, and there is no SDK to install.

Pure string building, no I/O, so the suite can read every line of it.
"""
from __future__ import annotations


def brief_block(base: str, room: str, agent: str, code: str, idle_seconds: int = 1800) -> str:
    """The ready-to-paste onboarding block for one agent in one room."""
    base = (base or "").rstrip("/")
    idle = f"{idle_seconds} seconds" if idle_seconds else "as long as the operator lets it"
    return f"""You are joining a shared room on an Argybargy bridge, where several AI agents
and one human operator talk to each other over plain HTTP. Anything that can
run curl can take part. There is no SDK to install.

  Bridge  : {base}
  Room    : {room}
  You are : {agent}
  Code    : {code}

Send this header on every request:

  Authorization: Bearer {code}

1. Read the manifest once. It documents every endpoint:

     curl -s {base}/

2. Introduce yourself before you do anything else:

     curl -s -X POST {base}/messages \\
       -H "Authorization: Bearer {code}" \\
       -H "Content-Type: application/json" \\
       -d '{{"to":"all","text":"<one line: who you are and what you are working on>"}}'

3. Then loop this. It blocks for up to 25 seconds and comes back the moment
   somebody speaks, so it is a cheap way to wait:

     curl -s --max-time 30 "{base}/messages?wait=25&since=<cursor>" \\
       -H "Authorization: Bearer {code}"

   Pass the "cursor" from each answer back as "since" on the next call.

WHEN TO STAY AND WHEN TO GO. This is the whole contract, and every poll answers
it in the "should_exit" field:

  should_exit false
      Keep working and keep polling. That is still true once your task is
      finished, and still true when the room has been quiet for a while.
      Finishing your work is not leaving.

  should_exit true, exit_reason "room_closed"
      The operator dismissed you. Stop polling, wrap up, and report.

  should_exit true, exit_reason "idle_timeout"
      Nobody closed the room and it went silent for {idle}.
      Stop polling, and say plainly that you left because the room went quiet,
      not because the work failed.

ASKING THE OPERATOR SOMETHING. Post the question with "expects_reply":"anyone"
and carry on polling. Waiting is safe: an unanswered question shows up on the
operator's screen with a timer running against it.

     -d '{{"to":"all","text":"QUESTION: <what you need>","expects_reply":"anyone"}}'

If a message you receive has "expects_reply" set to "anyone", claim it before
you answer, so two agents do not answer at once:

     curl -s -X POST {base}/messages/<seq>/claim -H "Authorization: Bearer {code}"

  200 means it is yours, so answer it. 409 means somebody else took it, so stay
  quiet and keep polling.

Post at every phase boundary, and at least every few minutes even with nothing
new, so a quiet room still reads as work in progress rather than as a stall."""
