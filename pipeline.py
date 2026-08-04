from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from artifacts import write_release_artifact
from brand_rules import BANNED_TERMS, ENTITY_FORBIDDEN
from config import Config
from content_calendar import (
    Topic,
    get_next_topic,
    load_calendar,
    mark_in_progress,
    mark_release_ready,
    mark_retry_pending,
    mark_skipped,
    slugify,
)
from evidence import build_evidence_report
from exceptions import (
    CalendarExhaustedError,
    ContentEngineError,
    ProviderUnavailableError,
    RefusalError,
    ValidationError,
)
from generator import generate, regenerate_for_quality
from notify import send_error, send_release_ready
from optimizer import optimize
from pre_publish_llm import PrePublishLLMResult, run_pre_publish_llm_test
from quality import gate
from research import enrich
from verify import check_preview_file

LOGGER = logging.getLogger("content_engine")
LOCK_PATH = Path(".content-engine.lock")
LOCK_METADATA_PATH = LOCK_PATH / "owner.json"
STALE_LOCK_MAX_AGE = timedelta(hours=6)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    config = Config.load()
    _configure_logging(config.pipeline.log_level)
    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = Path("logs") / "runs" / datetime.now().strftime("%Y-%m-%d")
    stage_timings: dict[str, float] = {}
    topic: Topic | None = None
    research_context = None
    quality_result = None
    artifact = None
    pre_publish_result = None
    evidence_report = None
    published_url = ""
    status = "started"
    lock_acquired = False

    try:
        _prune_old_logs(config.pipeline.max_log_age_days)
        _record_event(run_dir, {"run_id": run_id, "event": "run_started", "status": status})

        _time_stage(stage_timings, "acquire_lock", _acquire_lock, run_dir, run_id)
        lock_acquired = True
        topic = _time_stage(
            stage_timings,
            "select_topic",
            lambda: _select_topic(args, args.dry_run),
            run_dir,
            run_id,
        )

        if topic and not args.dry_run and args.topic is None:
            mark_in_progress(Path("content/calendar.yaml"), topic)

        research_context = _time_stage(
            stage_timings,
            "enrich_research",
            lambda: enrich(topic, config),
            run_dir,
            run_id,
        )
        _write_json(run_dir / "research-context.json", asdict(research_context))

        generated_content = None
        optimized_content = None
        quality_repair_failures: list[str] | None = None
        max_quality_attempts = 1 + config.pipeline.max_quality_repairs

        for quality_attempt in range(max_quality_attempts):
            generate_stage = _stage_name("generate_content", "repair_content", quality_attempt)
            optimize_stage = _stage_name("optimize_aeo", "repair_optimize_aeo", quality_attempt)
            quality_stage = _stage_name("quality_gate", "repair_quality_gate", quality_attempt)

            generated_content = _time_stage(
                stage_timings,
                generate_stage,
                lambda: (
                    generate(topic, research_context, config)
                    if quality_repair_failures is None
                    else regenerate_for_quality(
                        topic,
                        research_context,
                        config,
                        generated_content,
                        quality_repair_failures,
                    )
                ),
                run_dir,
                run_id,
            )
            _write_json(run_dir / "generated-content.json", asdict(generated_content))

            optimized_content = _time_stage(
                stage_timings,
                optimize_stage,
                lambda: optimize(generated_content, config),
                run_dir,
                run_id,
            )
            (run_dir / "optimized-content.html").write_text(optimized_content.body_html)

            evidence_report = build_evidence_report(
                optimized_content.body_html,
                research_context.source_candidates,
            )
            _write_json(run_dir / "evidence-report.json", evidence_report.to_dict())

            quality_result = _time_stage(
                stage_timings,
                quality_stage,
                lambda: gate(
                    optimized_content,
                    config,
                    research_context.brand_context,
                    evidence_report=evidence_report,
                ),
                run_dir,
                run_id,
            )
            _write_json(run_dir / "quality-report.json", asdict(quality_result))

            if quality_result.passed:
                break
            if quality_attempt < config.pipeline.max_quality_repairs:
                quality_repair_failures = list(dict.fromkeys(quality_result.failures))
                _record_event(
                    run_dir,
                    {
                        "run_id": run_id,
                        "event": "quality_repair_requested",
                        "attempt": quality_attempt + 1,
                        "topic": topic.title,
                        "failures": quality_repair_failures,
                    },
                )
                continue
            raise ValidationError("; ".join(quality_result.failures) or "Quality gate failed")

        if config.pipeline.pre_publish_llm_test:
            pre_publish_result = _run_pre_publish_llm_test_nonfatal(
                topic,
                stage_timings,
                run_dir,
                run_id,
            )

        artifact = _time_stage(
            stage_timings,
            "write_release_artifact",
            lambda: write_release_artifact(
                topic,
                optimized_content,
                quality_result,
                config,
                run_dir,
                run_id,
                evidence_report=evidence_report,
            ),
            run_dir,
            run_id,
        )
        _time_stage(
            stage_timings,
            "render_preview",
            lambda: check_preview_file(run_dir / "rendered-preview.html"),
            run_dir,
            run_id,
        )

        if not args.dry_run:
            if config.delivery.release_mode == "manual":
                send_release_ready(
                    topic,
                    artifact,
                    quality_result,
                    run_dir,
                    config,
                    pre_publish_result=pre_publish_result,
                )
            if args.topic is None:
                mark_release_ready(
                    Path("content/calendar.yaml"),
                    topic,
                    str(run_dir / "release-artifact.json"),
                    date.today().isoformat(),
                )
        status = "release_ready"
    except CalendarExhaustedError as exc:
        LOGGER.info("No pending topics remain: %s", exc)
        status = "empty"
        _record_error(run_dir, run_id, "select_topic", exc, topic)
    except FileExistsError:
        LOGGER.info("Another run is already in progress")
        status = "locked"
    except RefusalError as exc:
        status = "error"
        if topic and not args.dry_run and args.topic is None:
            mark_skipped(Path("content/calendar.yaml"), topic, str(exc))
        send_error("generate_content", exc, topic, config)
        _record_error(run_dir, run_id, "generate_content", exc, topic)
    except (
        ContentEngineError,
        FileNotFoundError,
        yaml.YAMLError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        status = "error"
        if (
            topic
            and not args.dry_run
            and args.topic is None
        ):
            if isinstance(exc, (ProviderUnavailableError, ValidationError)):
                mark_retry_pending(
                    Path("content/calendar.yaml"),
                    topic,
                    str(exc),
                    date.today().isoformat(),
                )
            else:
                mark_skipped(Path("content/calendar.yaml"), topic, str(exc))
        send_error(_stage_for_error(exc), exc, topic, config)
        _record_error(run_dir, run_id, _stage_for_error(exc), exc, topic)
    finally:
        _write_manifest(
            run_dir,
            {
                "run_id": run_id,
                "topic": topic.title if topic else None,
                "content_type": topic.content_type if topic else None,
                "stage_timings": stage_timings,
                "quality_score": quality_result.score if quality_result else None,
                "published": False,
                "url": published_url,
                "status": status,
                "error": None if status != "error" else "See logs",
                "research_degraded": research_context.degraded if research_context else None,
                "degradation_reason": (
                    research_context.degradation_reason if research_context else ""
                ),
                "release_artifact": str(run_dir / "release-artifact.json") if artifact else None,
                "evidence_report": (
                    str(run_dir / "evidence-report.json") if evidence_report else None
                ),
                "pre_publish_llm_test": (
                    str(run_dir / "pre-publish-llm-test.json") if pre_publish_result else None
                ),
                "preview_file": str(run_dir / "rendered-preview.html") if artifact else None,
                "events_file": str(run_dir / "run-events.jsonl"),
            },
        )
        _record_event(
            run_dir,
            {
                "run_id": run_id,
                "event": "run_completed",
                "status": status,
                "topic": topic.title if topic else None,
            },
        )
        if lock_acquired:
            _release_lock()

    LOGGER.info("Run complete: %s", status)
    return 0 if status in {"release_ready", "empty", "locked"} else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Folloze Content Engine")
    parser.add_argument("--topic")
    parser.add_argument("--type", dest="content_type")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date")
    return parser


def _configure_logging(level: str) -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("logs/content-engine.log"),
            logging.StreamHandler(),
        ],
    )


def _acquire_lock() -> None:
    try:
        os.mkdir(LOCK_PATH)
    except FileExistsError:
        if not _should_break_stale_lock():
            raise
        LOGGER.warning("Removing stale content-engine lock at %s", LOCK_PATH)
        _release_lock()
        os.mkdir(LOCK_PATH)
    _write_lock_metadata()


def _release_lock() -> None:
    if LOCK_PATH.exists():
        for child in LOCK_PATH.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)
        LOCK_PATH.rmdir()


def _write_lock_metadata() -> None:
    payload = {
        "pid": os.getpid(),
        "started_at": datetime.now().isoformat(),
        "command": sys.argv,
    }
    LOCK_METADATA_PATH.write_text(json.dumps(payload, indent=2))


def _should_break_stale_lock() -> bool:
    if not LOCK_PATH.exists():
        return False
    try:
        age = datetime.now() - datetime.fromtimestamp(LOCK_PATH.stat().st_mtime)
    except OSError:
        return False
    if age < STALE_LOCK_MAX_AGE:
        return False

    owner_pid = _read_lock_owner_pid()
    if owner_pid and _pid_is_running(owner_pid):
        return False

    return not _content_engine_process_active(exclude_pids={str(os.getpid())})


def _read_lock_owner_pid() -> int | None:
    try:
        payload = json.loads(LOCK_METADATA_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    pid = payload.get("pid")
    return pid if isinstance(pid, int) and pid > 0 else None


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _content_engine_process_active(exclude_pids: set[str] | None = None) -> bool:
    exclude = exclude_pids or set()
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False

    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid, _, command = stripped.partition(" ")
        if pid in exclude:
            continue
        if "pipeline.py" in command or "run_daily_publish.py" in command:
            return True
    return False


def _select_topic(args: argparse.Namespace, dry_run: bool) -> Topic:
    calendar_topics = load_calendar(Path("content/calendar.yaml"))
    if args.topic:
        requested_slug = slugify(args.topic)
        for topic in calendar_topics:
            if topic.title == args.topic or topic.slug == requested_slug:
                if args.content_type and topic.content_type != args.content_type:
                    raise ValueError(
                        f"--type {args.content_type!r} does not match calendar topic type "
                        f"{topic.content_type!r}"
                    )
                _validate_topic_for_generation(topic)
                return topic
        if not args.content_type:
            raise ValueError("--type is required when --topic is provided")
        topic = Topic(
            title=args.topic,
            content_type=args.content_type,
            slug=requested_slug,
            keywords=[requested_slug.replace("-", " ")],
            priority=5,
            status="pending",
            notes="manual topic override",
        )
        _validate_topic_for_generation(topic)
        return topic
    topic = get_next_topic(calendar_topics)
    _validate_topic_for_generation(topic)
    return topic


def _validate_topic_for_generation(topic: Topic) -> None:
    if not topic.keywords:
        raise ValidationError(f"Topic '{topic.title}' is missing keywords")

    primary_keyword = topic.keywords[0].strip().lower()
    combined_text = " ".join([topic.title, topic.notes, *topic.keywords]).lower()
    forbidden_hits = sorted({term for term in ENTITY_FORBIDDEN if term in combined_text})
    banned_hits = sorted({term for term in BANNED_TERMS if term in combined_text})

    if primary_keyword in ENTITY_FORBIDDEN or primary_keyword in BANNED_TERMS:
        raise ValidationError(
            f"Topic '{topic.title}' uses a forbidden primary keyword '{topic.keywords[0]}'. "
            "Rewrite the topic to use approved language and keep legacy terminology as "
            "search-intent only framing in notes/title if needed."
        )

    if topic.content_type == "glossary" and forbidden_hits and "search-intent only" not in topic.notes.lower():
        hits = ", ".join(sorted(set(forbidden_hits + banned_hits)))
        raise ValidationError(
            f"Glossary topic '{topic.title}' contains forbidden terminology ({hits}) without "
            "explicit search-intent only guidance in notes. Add that framing or rewrite the topic."
        )


def _time_stage(stage_timings: dict[str, float], name: str, func, run_dir: Path, run_id: str):
    LOGGER.info("stage=%s start", name)
    start = time.perf_counter()
    _record_event(run_dir, {"run_id": run_id, "event": "stage_started", "stage": name})
    try:
        result = func()
    except Exception as exc:
        duration = round(time.perf_counter() - start, 4)
        stage_timings[name] = duration
        _record_event(
            run_dir,
            {
                "run_id": run_id,
                "event": "stage_failed",
                "stage": name,
                "duration_seconds": duration,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        raise
    duration = round(time.perf_counter() - start, 4)
    stage_timings[name] = duration
    LOGGER.info("stage=%s done duration=%.4f", name, duration)
    _record_event(
        run_dir,
        {
            "run_id": run_id,
            "event": "stage_completed",
            "stage": name,
            "duration_seconds": duration,
        },
    )
    return result


def _stage_name(initial_stage: str, repair_stage: str, quality_attempt: int) -> str:
    if quality_attempt == 0:
        return initial_stage
    if quality_attempt == 1:
        return repair_stage
    return f"{repair_stage}_{quality_attempt}"


def _run_pre_publish_llm_test_nonfatal(
    topic: Topic,
    stage_timings: dict[str, float],
    run_dir: Path,
    run_id: str,
) -> PrePublishLLMResult:
    try:
        result = _time_stage(
            stage_timings,
            "pre_publish_llm_test",
            lambda: run_pre_publish_llm_test(topic),
            run_dir,
            run_id,
        )
    except Exception as exc:
        LOGGER.exception("Unexpected pre-publish LLM test failure; continuing degraded")
        keyword = topic.keywords[0].strip() if topic.keywords and topic.keywords[0].strip() else topic.title
        query = (
            f"For the query '{keyword}', what would a B2B marketing leader currently learn? "
            "Name relevant vendors if appropriate, cite sources when possible, and be concise."
        )
        result = PrePublishLLMResult(
            provider="perplexity",
            keyword=keyword,
            query=query,
            response_excerpt="",
            folloze_mentioned=False,
            competitors_mentioned=[],
            source_urls=[],
            recommendation="unknown",
            checked_at=datetime.now().astimezone().isoformat(),
            degraded=True,
            error=f"{type(exc).__name__}: {exc}",
        )
    _write_json(run_dir / "pre-publish-llm-test.json", result.to_dict())
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _write_manifest(run_dir: Path, payload: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "run-manifest.json", payload)


def _record_event(run_dir: Path, payload: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": datetime.now().isoformat(), **payload}
    with (run_dir / "run-events.jsonl").open("a") as handle:
        handle.write(json.dumps(event) + "\n")


def _record_error(
    run_dir: Path,
    run_id: str,
    stage: str,
    error: Exception,
    topic: Topic | None,
) -> None:
    _record_event(
        run_dir,
        {
            "run_id": run_id,
            "event": "run_error",
            "stage": stage,
            "topic": topic.title if topic else None,
            "error_type": type(error).__name__,
            "error": str(error),
        },
    )


def _prune_old_logs(max_age_days: int) -> None:
    runs_dir = Path("logs") / "runs"
    if not runs_dir.exists():
        return
    cutoff = date.today() - timedelta(days=max_age_days)
    for path in runs_dir.iterdir():
        if not path.is_dir():
            continue
        try:
            run_date = date.fromisoformat(path.name)
        except ValueError:
            continue
        if run_date < cutoff:
            for child in sorted(path.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            path.rmdir()


def _stage_for_error(error: Exception) -> str:
    if isinstance(error, ProviderUnavailableError):
        if "research" in str(error).lower():
            return "enrich_research"
        return "generate_content"
    if isinstance(error, ValidationError):
        message = str(error).lower()
        if any(
            token in message
            for token in (
                "generated content too short",
                "payload missing",
                "returned invalid json",
                "did not contain a json object",
            )
        ):
            return "generate_content"
        return "quality_gate"
    return "pipeline"


if __name__ == "__main__":
    raise SystemExit(main())
