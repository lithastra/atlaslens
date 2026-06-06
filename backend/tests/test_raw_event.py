from datetime import UTC, datetime, timedelta, timezone

from atlaslens.connectors.base import RawEvent


def _ev(dt: datetime) -> RawEvent:
    return RawEvent(source_id="x", occurred_at=dt, event_type="t", payload={})


def test_aware_non_utc_is_converted_to_utc() -> None:
    jst = timezone(timedelta(hours=9))
    ev = _ev(datetime(2026, 6, 6, 13, 17, 26, tzinfo=jst))
    assert ev.occurred_at.utcoffset() == timedelta(0)
    # same instant, expressed in UTC (13:17 JST == 04:17 UTC)
    assert ev.occurred_at == datetime(2026, 6, 6, 4, 17, 26, tzinfo=UTC)


def test_naive_is_assumed_utc() -> None:
    ev = _ev(datetime(2026, 6, 6, 4, 17, 26))
    assert ev.occurred_at.utcoffset() == timedelta(0)
    assert ev.occurred_at == datetime(2026, 6, 6, 4, 17, 26, tzinfo=UTC)


def test_utc_is_unchanged() -> None:
    dt = datetime(2026, 6, 6, 4, 17, 26, tzinfo=UTC)
    assert _ev(dt).occurred_at == dt
