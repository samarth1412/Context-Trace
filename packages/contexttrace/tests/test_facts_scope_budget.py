from time import perf_counter

from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2_1 import (
    fact_scope_complexity,
    observable_conflicts,
    verify_trace_v2_1,
)

CLAIM = (
    "The IRC_MESSAGE_TYPE, IRC_TARGET, IRC_SEND_TO, IRC_USER_KICKED, "
    "IRC_USER_HOST, IRC_USER_NICK, IRC_USER_SERVERNAME, IRC_USER_USERNAME, "
    "IRC_NUM and IRC_VALUE constants have been renamed to follow the Camel "
    "naming convention."
)
EVIDENCE = """
Constant Previous value New value
IRC_MESSAGE_TYPE irc.messageType CamelIrcMessageType
IRC_TARGET irc.target CamelIrcTarget
IRC_SEND_TO irc.sendTo CamelIrcSendTo
IRC_USER_KICKED irc.user.kicked CamelIrcUserKicked
IRC_USER_HOST irc.user.host CamelIrcUserHost
IRC_USER_NICK irc.user.nick CamelIrcUserNick
IRC_USER_SERVERNAME irc.user.servername CamelIrcUserServername
IRC_USER_USERNAME irc.user.username CamelIrcUserUsername
IRC_NUM irc.num CamelIrcNum
IRC_VALUE irc.value CamelIrcValue
"""


def test_v2_1_complex_fact_guard_routes_identifier_list_without_recursion() -> None:
    trace = RAGTrace(
        query="Which Camel IRC constants changed?",
        answer=CLAIM,
        contexts=[
            TraceContext(
                id="camel",
                text=EVIDENCE,
                metadata={"canonical": True, "current": True},
            )
        ],
    )

    started = perf_counter()
    result = verify_trace_v2_1(trace)
    elapsed = perf_counter() - started

    assert elapsed < 1.0
    assert fact_scope_complexity(CLAIM)["guarded"] is True
    guard = result["claims"][0]["deterministic"]["signals"]["complex_fact_guard"]
    assert guard["guarded"] is True
    assert result["claims"][0]["route"] == "unresolved"
    assert result["claims"][0]["green"] is False


def test_observable_conflict_guard_skips_unbounded_legacy_fact_expansion() -> None:
    started = perf_counter()
    conflicts = observable_conflicts(CLAIM, EVIDENCE)
    elapsed = perf_counter() - started

    assert elapsed < 1.0
    assert conflicts == []
