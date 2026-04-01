from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from citation_monitor.providers import PROVIDERS, AuthError, ProviderError
from citation_monitor.report import MonitorRunSummary, build_summary, fire_alerts
from citation_monitor.storage import (
    DB_PATH,
    PARSER_VERSION,
    CitationRow,
    complete_run,
    create_run,
    get_checked_variants_for_run,
    get_latest_incomplete_run,
    get_run_citation_stats,
    init_db,
    insert_citation,
    upsert_competitor_sighting,
)
from citation_monitor.variants import get_variants_for_prompt, load_prompt_library
from config import Config

LOGGER = logging.getLogger("content_engine.citation_monitor")


class CitationMonitor:
    def __init__(self, db_path=DB_PATH, providers=None, dry_run: bool = False):
        self.db_path = Path(db_path)
        self.providers = self._normalize_providers(providers)
        self.dry_run = dry_run
        self.config = Config.load(Path("config.yaml"))
        self._failure_count = 0
        self._resume_enabled = False

    def run(self, resume: bool = False) -> MonitorRunSummary:
        prompts = load_prompt_library()
        if not prompts:
            raise ValueError("Prompt library is empty or missing")

        self._failure_count = 0
        self._resume_enabled = resume
        conn = init_db(self.db_path)
        run_date = date.today().isoformat()
        run_id: int | None = None

        try:
            if resume:
                run_id = get_latest_incomplete_run(conn)
                if run_id is not None:
                    row = conn.execute(
                        "SELECT run_date FROM monitor_runs WHERE id = ?",
                        (run_id,),
                    ).fetchone()
                    if row and row[0]:
                        run_date = row[0]
                    LOGGER.info("Resuming incomplete citation monitor run id=%s", run_id)

            if run_id is None:
                run_id = create_run(conn, run_date)
                LOGGER.info("Created citation monitor run id=%s for %s", run_id, run_date)

            for prompt in prompts:
                self._run_prompt(conn, run_id, prompt, self.providers)

            summary = build_summary(
                conn=conn,
                run_id=run_id,
                run_date=run_date,
                prompts=prompts,
                failure_count=self._failure_count,
            )
            alert_fired = False if self.dry_run else fire_alerts(summary, self.config)
            stats = get_run_citation_stats(conn, run_id)
            complete_run(
                conn=conn,
                run_id=run_id,
                prompt_count=summary.prompts_checked,
                citation_count=stats["mentioned"],
                alert_fired=alert_fired,
                summary_json=json.dumps(asdict(summary), sort_keys=True),
            )
            return summary
        finally:
            conn.close()

    def _run_prompt(self, conn, run_id, prompt, providers) -> None:
        prompt_id = prompt["prompt_id"]
        if self.dry_run:
            variants = [prompt["canonical_text"]]
        else:
            variants = get_variants_for_prompt(
                conn,
                prompt,
                max_variants=int(prompt.get("variants_count", 5)),
            )
        checked_by_provider = {
            provider: (
                get_checked_variants_for_run(conn, run_id, prompt_id, provider)
                if self._resume_enabled
                else set()
            )
            for provider in providers
        }

        for variant_text in variants:
            for provider in providers:
                if variant_text in checked_by_provider[provider]:
                    LOGGER.info(
                        "Skipping already checked variant prompt_id=%s provider=%s",
                        prompt_id,
                        provider,
                    )
                    continue

                try:
                    if self.dry_run:
                        row = self._build_dry_run_row(run_id, prompt_id, variant_text, provider)
                    else:
                        result = PROVIDERS[provider](variant_text)
                        row = CitationRow(
                            run_id=run_id,
                            prompt_id=prompt_id,
                            variant_text=variant_text,
                            provider=provider,
                            response_text=result.response_text,
                            folloze_mentioned=result.folloze_mentioned,
                            folloze_cited=result.folloze_cited,
                            folloze_citation_position=result.folloze_citation_position,
                            branded="folloze" in variant_text.lower(),
                            competitors_mentioned=result.competitors_mentioned,
                            confidence_flag=result.confidence_flag,
                            citation_probability=1.0 if result.folloze_mentioned else 0.0,
                            parser_version=PARSER_VERSION,
                            detection_method="regex",
                            checked_at=datetime.now(UTC).isoformat(),
                        )
                except AuthError:
                    LOGGER.exception(
                        "Auth error querying provider=%s prompt_id=%s; aborting run",
                        provider,
                        prompt_id,
                    )
                    raise
                except ProviderError as exc:
                    self._failure_count += 1
                    LOGGER.warning(
                        "Provider failure provider=%s prompt_id=%s variant=%r: %s",
                        provider,
                        prompt_id,
                        variant_text,
                        exc,
                    )
                    continue

                insert_citation(conn, row)
                checked_by_provider[provider].add(variant_text)
                for competitor in row.competitors_mentioned:
                    upsert_competitor_sighting(
                        conn=conn,
                        run_id=run_id,
                        prompt_id=prompt_id,
                        competitor=competitor,
                        sighting_count=1,
                        checked_at=row.checked_at,
                    )
                if not self.dry_run:
                    time.sleep(1.0)

    def _build_dry_run_row(
        self,
        run_id: int,
        prompt_id: str,
        variant_text: str,
        provider: str,
    ) -> CitationRow:
        branded = "folloze" in variant_text.lower()
        mentioned = branded
        checked_at = datetime.now(UTC).isoformat()
        return CitationRow(
            run_id=run_id,
            prompt_id=prompt_id,
            variant_text=variant_text,
            provider=provider,
            response_text=f"[dry-run] {provider} :: {variant_text}",
            folloze_mentioned=mentioned,
            folloze_cited=mentioned,
            folloze_citation_position=1 if mentioned else None,
            branded=branded,
            competitors_mentioned=[],
            confidence_flag="normal",
            citation_probability=1.0 if mentioned else 0.0,
            parser_version=PARSER_VERSION,
            detection_method="dry-run",
            checked_at=checked_at,
        )

    @staticmethod
    def _normalize_providers(providers) -> list[str]:
        if providers is None:
            return ["perplexity", "openai"]

        normalized = [str(provider).strip() for provider in providers if str(provider).strip()]
        unknown = [provider for provider in normalized if provider not in PROVIDERS]
        if unknown:
            raise ValueError(f"Unknown providers: {', '.join(unknown)}")
        return normalized
