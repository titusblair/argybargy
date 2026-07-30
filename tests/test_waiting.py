"""The operator inbox: who is blocked on a human, and for how long.

The rule under test is in ``hub.open_questions``: a question counts as answered
when the party it addressed speaks again in that room after it was asked. These
drive that rule directly (no clock, no database), then the two store queries that
feed it, then the shape ``/admin/state`` hands the dashboard.
"""
import datetime as dt

from argybargy.hub import open_questions
from argybargy.store import MessageStore

NOW = dt.datetime(2026, 7, 30, 12, 0, 0, tzinfo=dt.timezone.utc)


def q(seq, frm, expects, room="build", minutes_ago=1, text="ship it?", claimed_by=None):
    ts = (NOW - dt.timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")
    return {"room": room, "seq": seq, "ts": ts, "from": frm, "to": "all",
            "text": text, "expects_reply": expects, "claimed_by": claimed_by}


def ask(questions, last=None, members=None, statuses=None, **kw):
    return open_questions(questions, last or {}, members or {}, statuses or {}, now=NOW, **kw)


# ------------------------------------------------------- what counts as answered
def test_a_question_nobody_answered_is_listed():
    rows = ask([q(1, "claude", "operator")], members={"build": {"claude", "operator"}})
    assert [r["seq"] for r in rows] == [1]
    assert rows[0]["expects_reply_resolved"] == "operator"
    assert rows[0]["waiting_seconds"] == 60.0


def test_the_addressed_party_speaking_afterwards_answers_it():
    rows = ask([q(1, "claude", "operator")], last={"build": {"claude": 1, "operator": 2}})
    assert rows == []


def test_somebody_else_talking_does_not_answer_a_directed_question():
    """A busy room is not an answer. Only the party that was asked closes it."""
    rows = ask([q(1, "claude", "operator")], last={"build": {"claude": 1, "codex": 9}})
    assert [r["seq"] for r in rows] == [1]


def test_the_askers_own_follow_up_does_not_answer_their_own_question():
    rows = ask([q(1, "claude", "anyone")], last={"build": {"claude": 7}})
    assert [r["seq"] for r in rows] == [1]


def test_an_earlier_message_cannot_answer_a_later_question():
    """Strictly after. Otherwise a chatty room retroactively closes every question."""
    rows = ask([q(9, "claude", "operator")], last={"build": {"operator": 4}})
    assert [r["seq"] for r in rows] == [9]


def test_an_open_question_is_answered_by_anyone_but_the_asker():
    rows = ask([q(1, "claude", "anyone")], last={"build": {"claude": 1, "codex": 2}})
    assert rows == []


def test_anyone_narrows_to_the_only_other_member_and_that_name_must_answer():
    """Same narrowing the badge uses, so the row names who owes the reply."""
    members = {"build": {"claude", "operator"}}
    rows = ask([q(1, "claude", "anyone")], members=members)
    assert rows[0]["expects_reply_resolved"] == "operator"
    assert ask([q(1, "claude", "anyone")], last={"build": {"codex": 5}}, members=members)[0]["seq"] == 1
    assert ask([q(1, "claude", "anyone")], last={"build": {"operator": 5}}, members=members) == []


def test_a_message_that_expects_nothing_is_never_in_the_list():
    assert ask([q(1, "claude", "none"), q(2, "claude", "")]) == []


def test_a_closed_room_contributes_nothing():
    """Closing dismissed its agents, so nobody in there is still waiting on you."""
    statuses = {"build": {"status": "closed"}}
    assert ask([q(1, "claude", "operator")], statuses=statuses) == []
    assert len(ask([q(1, "claude", "operator")], statuses={"build": {"status": "open"}})) == 1


def test_a_claimed_but_unanswered_question_stays_and_says_who_claimed_it():
    """A claim is a promise, not an answer. The claimer going quiet is the bad case."""
    rows = ask([q(1, "claude", "anyone", claimed_by="codex")])
    assert rows[0]["claimed_by"] == "codex"


def test_a_question_the_operator_asked_is_not_in_the_operators_own_inbox():
    """'Waiting on you' means somebody is waiting on the human, not the reverse."""
    assert ask([q(1, "operator", "claude")]) == []
    assert len(ask([q(1, "claude", "operator")])) == 1


# ------------------------------------------------------------------- ordering
def test_the_longest_wait_comes_first():
    rows = ask([q(1, "a", "operator", room="r1", minutes_ago=2),
                q(2, "b", "operator", room="r2", minutes_ago=40),
                q(3, "c", "operator", room="r3", minutes_ago=9)])
    assert [r["room"] for r in rows] == ["r2", "r3", "r1"]
    assert rows[0]["waiting_seconds"] == 2400.0


def test_the_limit_keeps_the_longest_waits():
    rows = ask([q(i, f"a{i}", "operator", room=f"r{i}", minutes_ago=i) for i in range(1, 8)], limit=3)
    assert [r["room"] for r in rows] == ["r7", "r6", "r5"]


def test_no_limit_returns_everything():
    rows = ask([q(i, f"a{i}", "operator", room=f"r{i}") for i in range(1, 6)], limit=0)
    assert len(rows) == 5


def test_an_empty_relay_has_an_empty_inbox():
    assert ask([]) == []


# ------------------------------------------------------------ the store queries
def test_questions_returns_only_the_asking_messages(tmp_path):
    s = MessageStore(tmp_path / "w.db")
    s.add("build", "claude", "all", "just saying", "none")
    s.add("build", "claude", "all", "who takes this?", "anyone")
    s.add("ops", "codex", "operator", "approve?", "operator")
    rows = s.questions()
    assert [(r["room"], r["text"]) for r in rows] == [
        ("build", "who takes this?"), ("ops", "approve?")]
    assert rows[0]["expects_reply"] == "anyone"


def test_last_seq_by_sender_groups_per_room(tmp_path):
    s = MessageStore(tmp_path / "w.db")
    s.add("build", "claude", "all", "one", "none")
    s.add("build", "claude", "all", "two", "none")
    s.add("build", "codex", "all", "three", "none")
    s.add("ops", "claude", "all", "elsewhere", "none")
    assert s.last_seq_by_sender() == {"build": {"claude": 2, "codex": 3}, "ops": {"claude": 1}}


def test_the_two_queries_compose_into_a_real_answer(tmp_path):
    """End to end over a real database, no fixtures: ask, then answer, then gone."""
    s = MessageStore(tmp_path / "w.db")
    s.add("build", "claude", "all", "ready to migrate?", "operator")
    members = {"build": {"claude", "operator"}}
    assert len(open_questions(s.questions(), s.last_seq_by_sender(), members, {})) == 1
    s.add("build", "operator", "claude", "hold off", "none")
    assert open_questions(s.questions(), s.last_seq_by_sender(), members, {}) == []


# --------------------------------------------------------------- the API shape
def test_admin_state_carries_the_waiting_list(client, admin_headers):
    room = "waitapi"
    code = client.post("/admin/invite", headers=admin_headers,
                       json={"name": "waiter", "room": room}).json()["code"]
    auth = {"Authorization": f"Bearer {code}"}
    client.post("/messages", headers=auth,
                json={"to": "all", "text": "which provider?", "expects_reply": "anyone"})

    mine = [w for w in client.get("/admin/state", headers=admin_headers).json()["waiting"]
            if w["room"] == room]
    assert len(mine) == 1
    assert mine[0]["from"] == "waiter"
    assert mine[0]["text"] == "which provider?"
    assert mine[0]["waiting_seconds"] >= 0

    client.post("/admin/say", headers=admin_headers,
                json={"room": room, "to": "waiter", "text": "the second one"})
    assert [w for w in client.get("/admin/state", headers=admin_headers).json()["waiting"]
            if w["room"] == room] == []
    client.post("/admin/revoke", headers=admin_headers, json={"target": "waiter"})


def test_the_waiting_list_is_not_scoped_by_the_room_query(client, admin_headers):
    """The whole point is the room you are NOT looking at."""
    code = client.post("/admin/invite", headers=admin_headers,
                       json={"name": "elsewhere", "room": "waitfar"}).json()["code"]
    client.post("/messages", headers={"Authorization": f"Bearer {code}"},
                json={"to": "all", "text": "blocked over here", "expects_reply": "anyone"})
    state = client.get("/admin/state?room=default", headers=admin_headers).json()
    assert any(w["room"] == "waitfar" for w in state["waiting"])
    client.post("/admin/revoke", headers=admin_headers, json={"target": "elsewhere"})
