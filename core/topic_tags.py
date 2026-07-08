"""Broad topic tags for analytics when area keyword scoring returns uncategorized."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

TITLE_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "for",
    "with",
    "from",
    "into",
    "via",
    "using",
    "based",
    "toward",
    "towards",
    "through",
    "over",
    "under",
    "between",
    "across",
    "new",
    "fast",
    "efficient",
    "scalable",
    "system",
    "systems",
    "approach",
    "design",
    "framework",
    "method",
    "methods",
    "paper",
    "study",
    "analysis",
    "toward",
    "large",
    "small",
    "high",
    "low",
    "first",
    "general",
    "automatic",
    "automated",
    "towards",
    "what",
    "how",
    "why",
    "when",
    "where",
    "can",
    "does",
    "are",
    "is",
    "in",
    "on",
    "at",
    "to",
    "of",
}


@dataclass(frozen=True)
class TopicSpec:
    topic_id: str
    label: str
    keywords: tuple[str, ...]
    parent_area_id: str | None = None


# Broad systems topics for title/abstract matching (analytics only).
# ``parent_area_id`` links a topic to a hub research area (e.g. memory-resource).
TOPIC_SPECS: tuple[TopicSpec, ...] = (
    TopicSpec("memory-cache", "Memory management", ("cache", "caching", "memory", "dram", "sram", "prefetch", "hbm", "numa"), "memory-resource"),
    TopicSpec("compiler", "Compiler & IR", ("compiler", "compilation", "llvm", "mlir", "jit", "translator", "translation", "ir ")),
    TopicSpec("concurrency", "Concurrency", ("concurrency", "concurrent", "parallel", "parallelism", "thread", "locking", "synchronization", "race", "deadlock"), "os-kernel-arch"),
    TopicSpec("network", "Networking", ("network", "networking", "tcp", "udp", "routing", "datacenter", "rdma", "bandwidth", "latency")),
    TopicSpec("storage-db", "Storage & DB", ("storage", "database", "filesystem", "file system", "ssd", "nvme", "kv store", "sql", "transaction"), "fs-storage"),
    TopicSpec("hardware", "Hardware & accelerators", ("gpu", "cpu", "fpga", "asic", "wafer", "chip", "accelerator", "npu", "tpu", "hardware"), "on-device-ai"),
    TopicSpec("scheduling", "Scheduling", ("scheduling", "scheduler", "resource allocation", "load balancing", "orchestration"), "memory-resource"),
    TopicSpec("virtualization", "Virtualization", ("virtualization", "virtual machine", "container", "hypervisor", "vm ", "kvm"), "os-kernel-arch"),
    TopicSpec("formal", "Formal methods", ("formal", "verification", "model checking", "proof", "smt", "symbolic execution")),
    TopicSpec("quantum", "Quantum", ("quantum", "qubit", "qubits")),
    TopicSpec("privacy-crypto", "Privacy & crypto", ("privacy", "encryption", "homomorphic", "cryptograph", "crypto", "differential privacy"), "system-security"),
    TopicSpec("ml-systems", "ML systems", ("machine learning", "deep learning", "neural", "inference", "training", "llm", "transformer"), "llm-serving"),
    TopicSpec("security", "Security", ("security", "attack", "defense", "vulnerability", "exploit", "malware", "intrusion", "side-channel"), "system-security"),
    TopicSpec("os-kernel", "OS & kernel", ("operating system", "kernel", "syscall", "microkernel", "monolithic", "linux"), "os-kernel-arch"),
    TopicSpec("distributed", "Distributed systems", ("distributed", "consensus", "replication", "fault tolerance", "byzantine", "raft", "paxos"), "fault-tolerance"),
    TopicSpec("energy-power", "Energy & power", ("energy", "power", "battery", "thermal", "carbon"), "memory-resource"),
    TopicSpec("testing-debug", "Testing & debugging", ("testing", "debugging", "fuzz", "fuzzing", "sanitizer", "bug")),
    TopicSpec("program-analysis", "Program analysis", ("program analysis", "static analysis", "dynamic analysis", "taint", "pointer analysis"), "system-security"),
    TopicSpec("blockchain", "Blockchain", ("blockchain", "smart contract", "cryptocurrency")),
    TopicSpec("web-mobile", "Web & mobile", ("web", "browser", "mobile", "android", "ios", "javascript")),
)

TOPIC_BY_ID: dict[str, TopicSpec] = {spec.topic_id: spec for spec in TOPIC_SPECS}
TOPIC_ID_BY_LABEL: dict[str, str] = {spec.label: spec.topic_id for spec in TOPIC_SPECS}

WORD_RE = re.compile(r"[a-z0-9][a-z0-9+\-/]*[a-z0-9]|[a-z0-9]", re.I)


def _normalize_text(*parts: str) -> str:
    return " ".join(p.strip().lower() for p in parts if p and p.strip())


def match_topic_hits(text: str, *, max_tags: int = 4) -> list[TopicSpec]:
    """Return matched topic specs, strongest first."""
    haystack = _normalize_text(text)
    if not haystack:
        return []
    hits: list[tuple[int, TopicSpec]] = []
    for spec in TOPIC_SPECS:
        score = 0
        for kw in spec.keywords:
            if kw in haystack:
                score += len(kw)
        if score:
            hits.append((score, spec))
    hits.sort(key=lambda item: (-item[0], item[1].label))
    out: list[TopicSpec] = []
    seen: set[str] = set()
    for _score, spec in hits:
        if spec.topic_id in seen:
            continue
        seen.add(spec.topic_id)
        out.append(spec)
        if len(out) >= max_tags:
            break
    return out


def match_topic_tags(text: str, *, max_tags: int = 4) -> list[str]:
    return [spec.label for spec in match_topic_hits(text, max_tags=max_tags)]


def topic_matrix_key(topic_id: str) -> str:
    return f"topic:{topic_id}"


def parent_area_for_topic(topic_id: str) -> str | None:
    spec = TOPIC_BY_ID.get(topic_id)
    return spec.parent_area_id if spec else None


def significant_title_tokens(title: str, *, max_tokens: int = 3) -> list[str]:
    """Fallback tags from title tokens when lexicon misses."""
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in WORD_RE.findall(title.lower()):
        token = raw.strip("-/")
        if len(token) < 4 or token in TITLE_STOPWORDS or token.isdigit():
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    tokens.sort(key=lambda t: (-len(t), t))
    return [t.replace("-", " ") for t in tokens[:max_tokens]]


def extract_paper_topic_hits(
    *,
    title: str,
    abstract: str = "",
    venue: str = "",
    max_tags: int = 4,
) -> list[TopicSpec]:
    """Topic hits for analytics; used especially when area scoring is uncategorized."""
    text = _normalize_text(title, abstract, venue)
    hits = match_topic_hits(text, max_tags=max_tags)
    if hits:
        return hits
    fallback = significant_title_tokens(title, max_tokens=max_tags)
    if fallback:
        return [
            TopicSpec(
                topic_id=f"title:{token.lower().replace(' ', '-')}",
                label=token.title(),
                keywords=(),
            )
            for token in fallback
        ]
    if venue.strip():
        return [TopicSpec(topic_id="venue", label=venue.strip(), keywords=())]
    return []


def extract_paper_topic_tags(
    *,
    title: str,
    abstract: str = "",
    venue: str = "",
    max_tags: int = 4,
) -> list[str]:
    return [spec.label for spec in extract_paper_topic_hits(title=title, abstract=abstract, venue=venue, max_tags=max_tags)]


def aggregate_topic_counts(tag_lists: Iterable[list[str]]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for tags in tag_lists:
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
