from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from citation_monitor import monitor as monitor_mod
from citation_monitor import providers, report, variants
from citation_monitor.storage import (
    PARSER_VERSION,
    CitationRow,
    complete_run,
    create_run,
    get_cached_variants,
    get_checked_variants_for_run,
    get_latest_incomplete_run,
    get_run_citation_stats,
    get_run_source_attribution_summary,
    init_db,
    insert_citation,
    upsert_competitor_sighting,
    upsert_variant,
)


def _prompt(
    prompt_id: str = "t1-001",
    canonical_text: str = "What is the best AI marketing platform for B2B?",
    cluster: str = "ai-campaigns",
    intent_type: str = "vendor-evaluation",
    tier: str = "tier1",
    keywords: list[str] | None = None,
    variants_count: int = 5,
) -> dict:
    return {
        "prompt_id": prompt_id,
        "canonical_text": canonical_text,
        "cluster": cluster,
        "intent_type": intent_type,
        "funnel_stage": "solution-aware",
        "tier": tier,
        "priority": "critical",
        "search_volume": 100,
        "keywords": keywords or ["ai marketing platform"],
        "expected_folloze_presence": True,
        "target_competitors": ["mutiny", "demandbase"],
        "variants_count": variants_count,
    }


def _citation_row(
    run_id: int,
    prompt_id: str = "t1-001",
    variant_text: str = "What is the best AI marketing platform for B2B?",
    provider: str = "perplexity",
    folloze_mentioned: bool = True,
    folloze_cited: bool | None = None,
    branded: bool = False,
    competitors_mentioned: list[str] | None = None,
    sentiment_label: str | None = None,
    source_urls: list[str] | None = None,
) -> CitationRow:
    mentioned = folloze_mentioned
    return CitationRow(
        run_id=run_id,
        prompt_id=prompt_id,
        variant_text=variant_text,
        provider=provider,
        response_text="Folloze is a strong fit. Source: https://www.folloze.com/insights/example",
        folloze_mentioned=mentioned,
        folloze_cited=mentioned if folloze_cited is None else folloze_cited,
        folloze_citation_position=1 if mentioned else None,
        branded=branded,
        competitors_mentioned=competitors_mentioned or [],
        confidence_flag="normal",
        sentiment_label=sentiment_label or ("positive" if mentioned else "neutral"),
        source_urls=source_urls if source_urls is not None else (["https://www.folloze.com/insights/example"] if mentioned else []),
        citation_probability=1.0 if mentioned else 0.0,
        parser_version=PARSER_VERSION,
        detection_method="regex",
        checked_at="2026-04-01T10:00:00",
    )


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400 and self.status_code != 429:
            raise providers.requests.HTTPError(f"status={self.status_code}")

    def json(self) -> dict:
        return self._payload


def test_init_db_creates_tables(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert {
        "schema_version",
        "monitor_runs",
        "prompt_variants",
        "citation_results",
        "competitor_sightings",
    } <= tables


def test_create_and_complete_run(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    run_id = create_run(conn, "2026-04-01")
    complete_run(
        conn,
        run_id,
        prompt_count=3,
        citation_count=2,
        alert_fired=True,
        summary_json="{}",
    )
    row = conn.execute(
        (
            "SELECT prompt_count, citation_count, alert_fired, completed "
            "FROM monitor_runs WHERE id = ?"
        ),
        (run_id,),
    ).fetchone()
    assert row == (3, 2, 1, 1)


def test_insert_citation_and_query(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    run_id = create_run(conn, "2026-04-01")
    insert_citation(conn, _citation_row(run_id, competitors_mentioned=["mutiny"]))
    stats = get_run_citation_stats(conn, run_id)
    row = conn.execute(
        "SELECT prompt_id, provider, folloze_mentioned, competitors_mentioned, sentiment_label, source_urls FROM citation_results"
    ).fetchone()
    assert row[0] == "t1-001"
    assert row[1] == "perplexity"
    assert row[2] == 1
    assert json.loads(row[3]) == ["mutiny"]
    assert row[4] == "positive"
    assert json.loads(row[5]) == ["https://www.folloze.com/insights/example"]
    assert stats["mentioned"] == 1
    assert stats["brand_visibility_score"] == pytest.approx(1.0)
    assert stats["citation_rate"] == pytest.approx(1.0)


def test_source_attribution_summary(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    run_id = create_run(conn, "2026-04-01")
    insert_citation(conn, _citation_row(run_id, source_urls=["https://a.com", "https://b.com"]))
    insert_citation(conn, _citation_row(run_id, provider="openai", source_urls=["https://a.com"]))
    summary = get_run_source_attribution_summary(conn, run_id)
    assert summary[0] == {"url": "https://a.com", "count": 2}
    assert summary[1] == {"url": "https://b.com", "count": 1}


def test_upsert_variant_idempotent(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    upsert_variant(conn, "t1-001", "Variant A", "template")
    upsert_variant(conn, "t1-001", "Variant A", "template")
    count = conn.execute("SELECT COUNT(*) FROM prompt_variants").fetchone()[0]
    assert count == 1


def test_get_cached_variants_respects_age(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    upsert_variant(conn, "t1-001", "Fresh Variant", "template")
    upsert_variant(conn, "t1-001", "Stale Variant", "template")
    conn.execute(
        (
            "UPDATE prompt_variants "
            "SET created_date = datetime('now', '-10 days') "
            "WHERE variant_text = ?"
        ),
        ("Stale Variant",),
    )
    conn.commit()
    assert get_cached_variants(conn, "t1-001", max_age_days=7) == ["Fresh Variant"]


def test_get_checked_variants_for_run(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    run_id = create_run(conn, "2026-04-01")
    insert_citation(conn, _citation_row(run_id, variant_text="Variant A", provider="perplexity"))
    insert_citation(conn, _citation_row(run_id, variant_text="Variant B", provider="openai"))
    checked = get_checked_variants_for_run(conn, run_id, "t1-001", "perplexity")
    assert checked == {"Variant A"}


def test_get_latest_incomplete_run(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    old_run = create_run(conn, "2026-04-01")
    new_run = create_run(conn, "2026-04-02")
    complete_run(
        conn,
        old_run,
        prompt_count=1,
        citation_count=0,
        alert_fired=False,
        summary_json="{}",
    )
    assert get_latest_incomplete_run(conn) == new_run


def test_query_perplexity_folloze_mentioned(monkeypatch) -> None:
    monkeypatch.setattr(providers, "get_secret", lambda env_name: "token")
    monkeypatch.setattr(
        providers.requests,
        "post",
        lambda *args, **kwargs: DummyResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": "Folloze is the strongest fit.\nSource: https://www.folloze.com/insights/example\nMutiny is also an option."
                        }
                    }
                ]
            },
        ),
    )
    result = providers.query_perplexity("best ai marketing platform")
    assert result.folloze_mentioned is True
    assert result.folloze_cited is True
    assert result.folloze_citation_position == 1
    assert "mutiny" in result.competitors_mentioned
    assert result.sentiment_label == "positive"
    assert result.source_urls == ["https://www.folloze.com/insights/example"]


def test_query_perplexity_no_mention(monkeypatch) -> None:
    monkeypatch.setattr(providers, "get_secret", lambda env_name: "token")
    monkeypatch.setattr(
        providers.requests,
        "post",
        lambda *args, **kwargs: DummyResponse(
            200,
            {"choices": [{"message": {"content": "Demandbase is a strong enterprise choice."}}]},
        ),
    )
    result = providers.query_perplexity("best ai marketing platform")
    assert result.folloze_mentioned is False
    assert result.competitors_mentioned == ["demandbase"]
    assert result.sentiment_label == "neutral"


def test_query_perplexity_rate_limit_retry(monkeypatch) -> None:
    monkeypatch.setattr(providers, "get_secret", lambda env_name: "token")
    sleeps: list[float] = []
    responses = iter(
        [
            DummyResponse(429),
            DummyResponse(
                200,
                {"choices": [{"message": {"content": "Folloze is recommended."}}]},
            ),
        ]
    )
    monkeypatch.setattr(providers.requests, "post", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(providers.time, "sleep", lambda value: sleeps.append(value))
    result = providers.query_perplexity("best ai marketing platform")
    assert result.folloze_mentioned is True
    assert sleeps == [providers.BACKOFF_BASE**1]


def test_query_perplexity_auth_error(monkeypatch) -> None:
    monkeypatch.setattr(providers, "get_secret", lambda env_name: "token")
    monkeypatch.setattr(providers.requests, "post", lambda *args, **kwargs: DummyResponse(401))
    with pytest.raises(providers.AuthError):
        providers.query_perplexity("best ai marketing platform")


def test_query_perplexity_malformed_json(monkeypatch) -> None:
    monkeypatch.setattr(providers, "get_secret", lambda env_name: "token")
    monkeypatch.setattr(providers.requests, "post", lambda *args, **kwargs: DummyResponse(200, {}))
    with pytest.raises(providers.ProviderError, match="malformed JSON"):
        providers.query_perplexity("best ai marketing platform")


def test_openai_gateway_fallback(monkeypatch) -> None:
    class FakeGateway:
        def __init__(self, profile: str):
            assert profile == "openai"

        def chat(self, messages, max_tokens: int, temperature: float, timeout: int) -> str:
            return "Folloze is the best fit for enterprise teams."

    monkeypatch.setattr(providers, "hydrate_provider_env", lambda: None)
    monkeypatch.setattr(providers, "LLMGateway", FakeGateway)
    result = providers.query_openai_gateway("best ai marketing platform")
    assert result.provider == "openai"
    assert result.folloze_mentioned is True
    assert result.sentiment_label == "positive"


def test_get_variants_uses_cache(tmp_path: Path, monkeypatch) -> None:
    conn = init_db(tmp_path / "citation.db")
    prompt = _prompt()
    for index in range(1, 5):
        upsert_variant(conn, prompt["prompt_id"], f"Cached {index}", "template")

    monkeypatch.setattr(
        variants,
        "_generate_variants_llm",
        lambda canonical, prompt, count: (_ for _ in ()).throw(
            AssertionError("should not call llm")
        ),
    )
    result = variants.get_variants_for_prompt(conn, prompt, max_variants=5)
    assert result == [
        prompt["canonical_text"],
        "Cached 1",
        "Cached 2",
        "Cached 3",
        "Cached 4",
    ]


def test_get_variants_template_fallback(tmp_path: Path, monkeypatch) -> None:
    conn = init_db(tmp_path / "citation.db")
    prompt = _prompt()
    monkeypatch.setattr(variants, "_generate_variants_llm", lambda canonical, prompt, count: [])
    monkeypatch.setattr(
        variants,
        "_generate_variants_template",
        lambda prompt, count: ["Template One", "Template Two"][:count],
    )
    result = variants.get_variants_for_prompt(conn, prompt, max_variants=3)
    rows = conn.execute(
        "SELECT variant_text, generation_method FROM prompt_variants ORDER BY id"
    ).fetchall()
    assert result == [prompt["canonical_text"], "Template One", "Template Two"]
    assert rows == [("Template One", "template"), ("Template Two", "template")]


def test_monitor_run_stores_results(project_root: Path, monkeypatch) -> None:
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    prompts = [
        _prompt("t1-001"),
        _prompt("t1-002", canonical_text="Folloze vs Mutiny", intent_type="comparison"),
    ]
    (prompts_dir / "prompt_library.json").write_text(
        json.dumps({"version": "1.0", "updated": "2026-04-01", "prompts": prompts}),
        encoding="utf-8",
    )

    db_path = project_root / "data" / "citation_monitor.db"
    monkeypatch.setattr(
        monitor_mod,
        "get_variants_for_prompt",
        lambda conn, prompt, max_variants=5: [
            prompt["canonical_text"],
            f"{prompt['prompt_id']} alt",
        ],
    )
    monkeypatch.setattr(monitor_mod, "fire_alerts", lambda summary, config, conn=None: False)
    monkeypatch.setattr(monitor_mod.time, "sleep", lambda value: None)

    def fake_provider(variant_text: str):
        mentioned = "folloze" in variant_text.lower() or "alt" in variant_text
        return SimpleNamespace(
            response_text=f"response for {variant_text}",
            folloze_mentioned=mentioned,
            folloze_cited=mentioned,
            folloze_citation_position=1 if mentioned else None,
            competitors_mentioned=["mutiny"] if "alt" in variant_text else [],
            confidence_flag="normal",
            sentiment_label="positive" if mentioned else "neutral",
            source_urls=["https://www.folloze.com/insights/example"] if "alt" in variant_text else [],
        )

    monkeypatch.setattr(monitor_mod, "PROVIDERS", {"perplexity": fake_provider})
    summary = monitor_mod.CitationMonitor(db_path=db_path, providers=["perplexity"]).run()

    conn = init_db(db_path)
    counts = conn.execute("SELECT COUNT(*) FROM citation_results").fetchone()[0]
    competitor_count = conn.execute(
        "SELECT SUM(sighting_count) FROM competitor_sightings"
    ).fetchone()[0]
    assert counts == 4
    assert competitor_count == 2
    assert summary.prompts_checked == 2
    assert summary.brand_visibility_score == pytest.approx(0.75)
    assert summary.citation_rate == pytest.approx(0.75)
    assert summary.failure_count == 0


def test_monitor_resume_skips_checked(project_root: Path, monkeypatch) -> None:
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    prompt = _prompt("t1-001")
    (prompts_dir / "prompt_library.json").write_text(
        json.dumps({"version": "1.0", "updated": "2026-04-01", "prompts": [prompt]}),
        encoding="utf-8",
    )

    db_path = project_root / "data" / "citation_monitor.db"
    conn = init_db(db_path)
    run_id = create_run(conn, "2026-04-01")
    insert_citation(conn, _citation_row(run_id, variant_text="skip me", provider="perplexity"))
    conn.close()

    calls: list[str] = []
    monkeypatch.setattr(
        monitor_mod,
        "get_variants_for_prompt",
        lambda conn, prompt, max_variants=5: ["skip me", "check me"],
    )
    monkeypatch.setattr(monitor_mod, "fire_alerts", lambda summary, config, conn=None: False)
    monkeypatch.setattr(monitor_mod.time, "sleep", lambda value: None)

    def fake_provider(variant_text: str):
        calls.append(variant_text)
        return SimpleNamespace(
            response_text="ok",
            folloze_mentioned=True,
            folloze_cited=True,
            folloze_citation_position=1,
            competitors_mentioned=[],
            confidence_flag="normal",
            sentiment_label="positive",
            source_urls=[],
        )

    monkeypatch.setattr(monitor_mod, "PROVIDERS", {"perplexity": fake_provider})
    summary = monitor_mod.CitationMonitor(
        db_path=db_path,
        providers=["perplexity"],
    ).run(resume=True)

    conn = init_db(db_path)
    total_rows = conn.execute("SELECT COUNT(*) FROM citation_results").fetchone()[0]
    completed = conn.execute(
        "SELECT completed FROM monitor_runs WHERE id = ?",
        (run_id,),
    ).fetchone()[0]
    assert calls == ["check me"]
    assert total_rows == 2
    assert completed == 1
    assert summary.prompts_checked == 1


def test_monitor_dry_run_skips_variant_generation(project_root: Path, monkeypatch) -> None:
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    prompt = _prompt("t1-001")
    (prompts_dir / "prompt_library.json").write_text(
        json.dumps({"version": "1.0", "updated": "2026-04-01", "prompts": [prompt]}),
        encoding="utf-8",
    )

    db_path = project_root / "data" / "citation_monitor.db"
    monkeypatch.setattr(
        monitor_mod,
        "get_variants_for_prompt",
        lambda conn, prompt, max_variants=5: (_ for _ in ()).throw(
            AssertionError("dry run should not generate variants")
        ),
    )

    summary = monitor_mod.CitationMonitor(
        db_path=db_path,
        providers=["perplexity"],
        dry_run=True,
    ).run()

    conn = init_db(db_path)
    row = conn.execute("SELECT variant_text, detection_method FROM citation_results").fetchone()
    assert row == (prompt["canonical_text"], "dry-run")
    assert summary.prompts_checked == 1


def test_build_summary_from_real_db(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "citation.db")
    run_id = create_run(conn, "2026-04-01")
    prompts = [
        _prompt("t1-001", cluster="ai-campaigns", tier="tier1"),
        _prompt("t2-001", cluster="personalization", tier="tier2"),
        _prompt("t3-001", cluster="competitive", tier="tier3"),
    ]
    insert_citation(conn, _citation_row(run_id, prompt_id="t1-001", branded=True))
    insert_citation(
        conn,
        _citation_row(run_id, prompt_id="t1-001", provider="openai", branded=True),
    )
    insert_citation(
        conn,
        _citation_row(
            run_id,
            prompt_id="t2-001",
            provider="perplexity",
            folloze_mentioned=False,
            folloze_cited=False,
            branded=False,
            competitors_mentioned=["mutiny"],
            sentiment_label="neutral",
            source_urls=[],
        ),
    )
    upsert_competitor_sighting(conn, run_id, "t2-001", "mutiny", 6, "2026-04-01T10:00:00")

    summary = report.build_summary(conn, run_id, "2026-04-01", prompts, failure_count=2)
    assert summary.prompts_checked == 3
    assert summary.brand_visibility_score == pytest.approx(2 / 3)
    assert summary.citation_rate == pytest.approx(2 / 3)
    assert summary.branded_prompt_visibility_score == pytest.approx(1.0)
    assert summary.non_branded_prompt_visibility_score == pytest.approx(0.0)
    assert summary.tier_breakdown["tier1"] == pytest.approx(1.0)
    assert summary.cluster_breakdown["competitive"] == pytest.approx(0.0)
    assert "t3-001" in summary.gaps
    assert summary.competitor_leading[0] == {
        "prompt_id": "t2-001",
        "competitor": "mutiny",
        "count": 6,
    }
    assert summary.source_attribution[0]["url"] == "https://www.folloze.com/insights/example"
    assert "COMPETITOR LEADING: mutiny" in summary.alerts
    assert "NON-BRANDED VISIBILITY GAP" in summary.alerts
    assert summary.incomplete is True
    assert summary.failure_count == 2


def test_fire_alerts_skips_non_weekly_runs(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setitem(
        sys.modules,
        "notify",
        SimpleNamespace(send_canary_report=lambda subject, body, config: sent.append((subject, body))),
    )

    summary = report.MonitorRunSummary(
        run_date="2026-04-12",
        prompts_checked=3,
        brand_visibility_score=0.31,
        citation_rate=0.12,
        share_of_voice=0.18,
        sentiment_score=0.8,
        branded_prompt_visibility_score=0.6,
        non_branded_prompt_visibility_score=0.22,
        tier_breakdown={"tier1": 0.3},
        cluster_breakdown={"ai-campaigns": 0.3},
        gaps=["t1-001"],
        competitor_leading=[{"prompt_id": "t1-001", "competitor": "mutiny", "count": 6}],
        source_attribution=[{"url": "https://www.folloze.com/insights/example", "count": 2}],
        alerts=["LOW SHARE OF VOICE"],
        incomplete=False,
        failure_count=0,
    )

    assert report.fire_alerts(summary, None) is False
    assert sent == []


def test_fire_alerts_sends_weekly_rollup_on_monday(monkeypatch, tmp_path: Path) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setitem(
        sys.modules,
        "notify",
        SimpleNamespace(send_canary_report=lambda subject, body, config: sent.append((subject, body))),
    )

    conn = init_db(tmp_path / "citation.db")
    previous = create_run(conn, "2026-04-14")
    complete_run(
        conn,
        previous,
        prompt_count=3,
        citation_count=1,
        alert_fired=False,
        summary_json=json.dumps(
            {
                "run_date": "2026-04-14",
                "prompts_checked": 3,
                "brand_visibility_score": 0.2,
                "citation_rate": 0.1,
                "share_of_voice": 0.15,
                "sentiment_score": 0.7,
                "branded_prompt_visibility_score": 0.4,
                "non_branded_prompt_visibility_score": 0.1,
                "tier_breakdown": {"tier1": 0.2},
                "cluster_breakdown": {"ai-campaigns": 0.2},
                "gaps": ["t1-001"],
                "competitor_leading": [{"prompt_id": "t1-001", "competitor": "mutiny", "count": 6}],
                "source_attribution": [{"url": "https://www.folloze.com/insights/example", "count": 2}],
                "alerts": ["LOW SHARE OF VOICE"],
                "incomplete": False,
                "failure_count": 0,
            }
        ),
    )

    latest = create_run(conn, "2026-04-20")
    complete_run(
        conn,
        latest,
        prompt_count=3,
        citation_count=1,
        alert_fired=False,
        summary_json=json.dumps(
            {
                "run_date": "2026-04-20",
                "prompts_checked": 3,
                "brand_visibility_score": 0.31,
                "citation_rate": 0.12,
                "share_of_voice": 0.18,
                "sentiment_score": 0.8,
                "branded_prompt_visibility_score": 0.6,
                "non_branded_prompt_visibility_score": 0.22,
                "tier_breakdown": {"tier1": 0.3},
                "cluster_breakdown": {"ai-campaigns": 0.3},
                "gaps": ["t1-001"],
                "competitor_leading": [{"prompt_id": "t1-001", "competitor": "mutiny", "count": 7}],
                "source_attribution": [{"url": "https://www.folloze.com/insights/example", "count": 3}],
                "alerts": ["LOW SHARE OF VOICE", "NON-BRANDED VISIBILITY GAP"],
                "incomplete": False,
                "failure_count": 0,
            }
        ),
    )

    summary = report.MonitorRunSummary(
        run_date="2026-04-20",
        prompts_checked=3,
        brand_visibility_score=0.31,
        citation_rate=0.12,
        share_of_voice=0.18,
        sentiment_score=0.8,
        branded_prompt_visibility_score=0.6,
        non_branded_prompt_visibility_score=0.22,
        tier_breakdown={"tier1": 0.3},
        cluster_breakdown={"ai-campaigns": 0.3},
        gaps=["t1-001"],
        competitor_leading=[{"prompt_id": "t1-001", "competitor": "mutiny", "count": 7}],
        source_attribution=[{"url": "https://www.folloze.com/insights/example", "count": 3}],
        alerts=["LOW SHARE OF VOICE", "NON-BRANDED VISIBILITY GAP"],
        incomplete=False,
        failure_count=0,
    )

    assert report.fire_alerts(summary, None, conn=conn) is True
    assert len(sent) == 1
    subject, body = sent[0]
    assert subject == "[Folloze GEO] Weekly Visibility Monitor — 2026-04-14 to 2026-04-20"
    assert "7-day rollup" in body
    assert "Latest run date" in body
    assert "2026-04-20" in body
    assert "<table" in body
    assert "Summary Metrics" in body
    assert "Executive Summary" in body
    assert "Daily Snapshots" in body
    assert "linear-gradient" in body
    assert "Generated for email-safe rendering" in body
    assert "Average Brand Visibility Score" in body
    assert "26%" in body
    assert "Average Citation Rate" in body
    assert "11%" in body
    assert "Average Share of Voice" in body
    assert "16%" in body
    assert "LOW SHARE OF VOICE" in body
    assert "1 run" in body
    assert "NON-BRANDED VISIBILITY GAP" in body
