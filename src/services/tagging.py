"""Local, deterministic description -> tag/category suggestions.

The lexicon is data, not code. Learned rules live in ``TagRules`` and are
scoped per user. No network calls are made here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from src.data.lexicon import load_lexicon, tag_id
from src.db.repo import append_rows, read_tab, update_row
from src.services.categories import find_category_by_name
from src.utils.ids import clean_text, new_id, now_iso

MAX_TAGS = 8
_FUZZY_MIN = 85
_WORD = re.compile(r"[^a-z0-9\u0900-\u097F]+")


@dataclass
class TagDef:
    tag_id: str
    name: str
    tag_type: str
    aliases: set[str] = field(default_factory=set)
    parent_id: str = ""
    category_name: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Suggestion:
    tag_ids: list[str] = field(default_factory=list)
    category_id: str = ""
    category_name: str = ""
    channel: str = ""
    merchant: str = ""
    service: str = ""
    confidence: float = 0.0
    reasons: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "tag_ids": self.tag_ids,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "channel": self.channel,
            "merchant": self.merchant,
            "service": self.service,
            "confidence": self.confidence,
            "reasons": self.reasons,
        }


def normalize(text: object) -> str:
    value = str(text or "").lower().replace("&", " and ")
    value = _WORD.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def _singular(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("oes") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _aliases_for(key: str, entry: dict | None, include_display: bool = True) -> set[str]:
    entry = entry or {}
    values = {key}
    if include_display and entry.get("display_name"):
        values.add(str(entry["display_name"]))
    values.update(str(alias) for alias in (entry.get("aliases") or []))
    normalized = set()
    for value in values:
        text = normalize(value)
        if text:
            normalized.add(text)
            normalized.add(" ".join(_singular(part) for part in text.split()))
    return normalized


def _add_tag(
    catalog: dict[str, TagDef],
    tid: str,
    name: str,
    tag_type: str,
    aliases: set[str],
    parent_id: str = "",
    category_name: str = "",
    metadata: dict | None = None,
) -> None:
    if not tid:
        return
    existing = catalog.get(tid)
    if existing:
        existing.aliases.update(aliases)
        if parent_id and not existing.parent_id:
            existing.parent_id = parent_id
        if category_name and not existing.category_name:
            existing.category_name = category_name
        if metadata:
            existing.metadata.update(metadata)
        return
    catalog[tid] = TagDef(
        tag_id=tid,
        name=name,
        tag_type=tag_type,
        aliases=aliases,
        parent_id=parent_id,
        category_name=category_name,
        metadata=metadata or {},
    )


def tag_catalog(user: str | None = None) -> dict[str, TagDef]:
    lexicon = load_lexicon()
    catalog: dict[str, TagDef] = {}

    for group, tag_type in (
        ("channels", "channel"),
        ("methods", "method"),
        ("services", "service"),
        ("merchants", "merchant"),
        ("items", "item"),
    ):
        for key, entry in (lexicon.get(group) or {}).items():
            tid = tag_id(tag_type, key)
            _add_tag(
                catalog,
                tid,
                key,
                tag_type,
                _aliases_for(key, entry),
                parent_id=tag_id("item", entry["parent"]) if entry.get("parent") else "",
                category_name=str(entry.get("category", "") or ""),
                metadata=entry,
            )

    # User-added / learned tags from the sheet.
    df = read_tab("Tags")
    if not df.empty:
        for row in df.to_dict("records"):
            if str(row.get("IsActive", "TRUE")).strip().lower() in {"false", "0", "no"}:
                continue
            tid = str(row.get("TagID", "")).strip()
            name = str(row.get("Name", "")).strip()
            tag_type = str(row.get("Type", "custom")).strip().lower() or "custom"
            if not tid or not name:
                continue
            aliases = {normalize(name)}
            for alias in str(row.get("Aliases", "")).split(","):
                text = normalize(alias)
                if text:
                    aliases.add(text)
            _add_tag(
                catalog,
                tid,
                name,
                tag_type,
                aliases,
                parent_id=str(row.get("ParentTag", "")).strip(),
                category_name="",
                metadata={"custom": True},
            )

    return catalog


def tag_name_map(user: str | None = None) -> dict[str, str]:
    return {tid: definition.name for tid, definition in tag_catalog(user).items()}


def tag_options(user: str | None = None) -> tuple[list[str], dict[str, str]]:
    catalog = tag_catalog(user)
    labels = {
        tid: f"{definition.name}  ·  {definition.tag_type}"
        for tid, definition in sorted(
            catalog.items(), key=lambda item: (item[1].tag_type, item[1].name)
        )
    }
    return list(labels.keys()), labels


def _word_match(alias: str, description: str) -> bool:
    return f" {alias} " in f" {description} "


def _fuzzy_match(alias: str, description: str) -> float:
    if len(alias) < 4:
        return 0.0
    best = 0.0
    tokens = description.split()
    grams: list[str] = []
    for size in (1, 2, 3):
        for index in range(0, max(0, len(tokens) - size + 1)):
            grams.append(" ".join(tokens[index : index + size]))
    for gram in grams:
        if len(gram) < 4:
            continue
        score = fuzz.ratio(alias, gram)
        if score > best:
            best = score
    return best if best >= _FUZZY_MIN else 0.0


def _match_catalog(description: str, catalog: dict[str, TagDef]) -> dict[str, tuple[float, str]]:
    matches: dict[str, tuple[float, str]] = {}
    for tid, definition in catalog.items():
        best = (0.0, "")
        for alias in definition.aliases:
            if not alias:
                continue
            if alias == description:
                score, reason = 1.0, "exact match"
            elif _word_match(alias, description):
                score, reason = 1.0, "matched word"
            elif alias in description:
                score, reason = 0.9, "matched phrase"
            else:
                fuzzy = _fuzzy_match(alias, description)
                score, reason = (0.7, "close spelling") if fuzzy else (0.0, "")
            if score > best[0]:
                best = (score, reason)
                if score >= 1.0:
                    break
        if best[0] > 0:
            matches[tid] = best
    return matches


def _learned_matches(
    user: str | None, description: str
) -> tuple[dict[str, tuple[float, str]], str]:
    if not user:
        return {}, ""
    df = read_tab("TagRules")
    if df.empty:
        return {}, ""
    matches: dict[str, tuple[float, str]] = {}
    category_id = ""
    for row in df.to_dict("records"):
        if str(row.get("User", "")).strip() != user:
            continue
        if str(row.get("IsActive", "TRUE")).strip().lower() in {"false", "0", "no"}:
            continue
        if str(row.get("Source", "")).strip().lower() not in {"learned", "manual"}:
            continue
        pattern = normalize(row.get("Pattern", ""))
        if not pattern:
            continue
        if _word_match(pattern, description) or pattern == description:
            for tid in str(row.get("OutputTagIDs", "")).split(","):
                tid = tid.strip()
                if tid:
                    matches[tid] = (0.8, "used before")
            if row.get("CategoryID"):
                category_id = str(row.get("CategoryID")).strip()
    return matches, category_id


def suggest_tags(
    description: str,
    user: str | None = None,
    entry_type: str = "expense",
    method: str = "",
) -> Suggestion:
    lexicon = load_lexicon()
    catalog = tag_catalog(user)
    desc = normalize(description)
    suggestion = Suggestion()

    if not desc:
        if method:
            mid = tag_id("method", method)
            if mid in catalog:
                suggestion.tag_ids.append(mid)
        return suggestion

    matches = _match_catalog(desc, catalog)

    learned, learned_category = _learned_matches(user, desc)
    for tid, value in learned.items():
        if tid in catalog:
            if tid not in matches or value[0] > matches[tid][0]:
                matches[tid] = value

    # Expand parent tags.
    expanded = dict(matches)
    for tid, (score, reason) in list(matches.items()):
        definition = catalog.get(tid)
        if definition and definition.tag_type == "item" and definition.parent_id:
            parent = catalog.get(definition.parent_id)
            if parent:
                parent_score = max(0.0, score - 0.05)
                if parent.tag_id not in expanded or parent_score > expanded[parent.tag_id][0]:
                    expanded[parent.tag_id] = (parent_score, f"parent of {definition.name}")
    matches = expanded

    # Pick merchant and service.
    merchant_id = ""
    merchant_score = 0.0
    for tid, (score, _) in matches.items():
        definition = catalog.get(tid)
        if definition and definition.tag_type == "merchant" and score > merchant_score:
            merchant_id = tid
            merchant_score = score
    merchant = catalog[merchant_id] if merchant_id else None
    merchant_meta = (merchant.metadata if merchant else {}) or {}

    service_id = ""
    service_score = 0.0
    for tid, (score, _) in matches.items():
        definition = catalog.get(tid)
        if definition and definition.tag_type == "service" and score > service_score:
            service_id = tid
            service_score = score

    item_tags = [
        (tid, score)
        for tid, (score, _) in matches.items()
        if (catalog.get(tid) and catalog[tid].tag_type == "item")
    ]
    item_category = ""
    item_reason = ""
    if item_tags:
        # Prefer specific item tags (non-parent) at the best score.
        parent_ids = {
            definition.parent_id
            for definition in catalog.values()
            if definition.tag_type == "item" and definition.parent_id
        }
        ranked = sorted(
            item_tags,
            key=lambda item: (
                item[1],
                catalog[item[0]].tag_id not in parent_ids,
                bool(catalog[item[0]].category_name),
            ),
            reverse=True,
        )
        for tid, score in ranked:
            definition = catalog[tid]
            if definition.category_name:
                item_category = definition.category_name
                item_reason = f"from item {definition.name}"
                break

    item_categories = {
        catalog[tid].category_name
        for tid, _ in item_tags
        if catalog.get(tid) and catalog[tid].category_name
    }

    chosen_service = None
    if service_id:
        chosen_service = catalog[service_id]
    elif merchant:
        category_services = merchant_meta.get("category_services") or {}
        if item_category and item_category in category_services:
            service_key = category_services[item_category]
            chosen_service = catalog.get(tag_id("service", service_key))
        elif merchant_meta.get("default_service"):
            chosen_service = catalog.get(tag_id("service", merchant_meta["default_service"]))

    if chosen_service:
        service_id = chosen_service.tag_id
        matches[service_id] = (max(service_score, 0.8), "merchant service")

    # A merchant service conflict resolves to one service, not several.
    for tid in [
        tid
        for tid, definition in catalog.items()
        if definition.tag_type == "service"
    ]:
        if chosen_service is None or tid != chosen_service.tag_id:
            matches.pop(tid, None)

    # Category: item evidence > service > merchant default > learned rule.
    category_name = item_category
    category_reason = item_reason
    if not category_name and chosen_service and chosen_service.category_name:
        category_name = chosen_service.category_name
        category_reason = f"from service {chosen_service.name}"
    if not category_name and merchant:
        category_name = str(merchant_meta.get("default_category", "") or "")
        category_reason = f"default for {merchant.name}"

    if not item_category and chosen_service and chosen_service.category_name:
        category_name = chosen_service.category_name
        category_reason = f"from service {chosen_service.name}"

    category_id_value = ""
    if learned_category:
        category_id_value = learned_category
        category_name = category_name or ""
    if category_name:
        category = find_category_by_name(category_name, "Expenditure")
        if category:
            category_id_value = str(category.get("CategoryID", ""))
            category_name = str(category.get("Category", category_name))
    elif not category_id_value:
        suggestion.category_name = ""

    # Channel.
    channel = ""
    channel_score = 0.0
    for tid, (score, _) in matches.items():
        definition = catalog.get(tid)
        if definition and definition.tag_type == "channel" and score > channel_score:
            channel = definition.name
            channel_score = score
    if chosen_service:
        channel = str(chosen_service.metadata.get("channel", "") or channel)
    if not channel and merchant:
        channel = str(merchant_meta.get("default_channel", "") or "")
    for tid in [
        tid
        for tid, definition in catalog.items()
        if definition.tag_type == "channel"
    ]:
        if not channel or tid != tag_id("channel", channel):
            matches.pop(tid, None)
    if channel:
        cid = tag_id("channel", channel)
        if cid in catalog:
            matches[cid] = (max(matches.get(cid, (0.0, ""))[0], 0.9), "channel")

    # Method tag from the explicit payment method (the UI field wins).
    if method:
        mid = tag_id("method", method)
        if mid in catalog:
            matches[mid] = (1.0, "payment method")

    # Keep the strongest tags, but never exceed the cap.
    ordered = sorted(
        matches.items(),
        key=lambda item: (
            -item[1][0],
            catalog[item[0]].tag_type if item[0] in catalog else "zzz",
            catalog[item[0]].name if item[0] in catalog else item[0],
        ),
    )
    selected: list[str] = []
    reasons: dict[str, str] = {}
    for tid, (_, reason) in ordered:
        if tid not in catalog:
            continue
        selected.append(tid)
        reasons[tid] = reason
        if len(selected) >= MAX_TAGS:
            break

    suggestion.tag_ids = selected
    suggestion.reasons = reasons
    suggestion.category_id = category_id_value
    suggestion.category_name = category_name
    suggestion.channel = channel
    suggestion.merchant = merchant.name if merchant else ""
    suggestion.service = chosen_service.name if chosen_service else ""
    suggestion.confidence = max((score for score, _ in matches.values()), default=0.0)
    return suggestion


def record_learning(
    user: str,
    description: str,
    tag_ids: list[str],
    category_id_value: str = "",
    channel: str = "",
) -> None:
    pattern = normalize(description)
    if not pattern or not tag_ids:
        return
    df = read_tab("TagRules")
    existing = None
    if not df.empty:
        for row in df.to_dict("records"):
            if (
                str(row.get("User", "")).strip() == user
                and normalize(row.get("Pattern", "")) == pattern
                and str(row.get("Source", "")).strip().lower() in {"learned", "manual"}
            ):
                existing = row
                break
    output = ", ".join(dict.fromkeys(tag_ids))
    if existing:
        existing["OutputTagIDs"] = output
        existing["CategoryID"] = category_id_value or existing.get("CategoryID", "")
        existing["Channel"] = channel or existing.get("Channel", "")
        existing["Hits"] = str(int(float(existing.get("Hits") or 0)) + 1)
        existing["LastUsed"] = now_iso()
        existing["IsActive"] = "TRUE"
        update_row("TagRules", "RuleID", str(existing.get("RuleID")), existing)
        return
    append_rows(
        "TagRules",
        [
            {
                "RuleID": new_id("rule"),
                "User": user,
                "Pattern": pattern,
                "MatchType": "contains",
                "OutputTagIDs": output,
                "Channel": channel,
                "CategoryID": category_id_value,
                "Priority": 10,
                "Source": "learned",
                "Hits": 1,
                "LastUsed": now_iso(),
                "IsActive": "TRUE",
            }
        ],
    )


def create_custom_tag(name: str, tag_type: str = "custom", aliases: str = "") -> dict:
    label = clean_text(name, 40).lower()
    if not label:
        raise ValueError("Tag name is required.")
    tid = tag_id(tag_type, re.sub(r"[^a-z0-9]+", "_", label).strip("_") or new_id("t"))
    row = {
        "TagID": tid,
        "Name": label,
        "Type": tag_type,
        "Aliases": aliases or label,
        "ParentTag": "",
        "DefaultCategoryID": "",
        "IsActive": "TRUE",
    }
    append_rows("Tags", [row])
    return row
