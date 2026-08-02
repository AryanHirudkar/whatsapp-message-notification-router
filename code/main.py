"""Application entry point.

Orchestrates configuration loading, data ingestion, message processing,
and output writing. Contains no business logic.
"""

import argparse
import os
import re
import sys
import json
import base64
import time
from pathlib import Path

from groq import Groq

from dotenv import load_dotenv
from code.config import Config, load_config
from code.data.context_builder import ContextBuilder
from code.data.indexer import MessageIndexer
from code.data.loader import DatasetLoader
from code.data.models import Message, MessageContext, Prediction
from code.output.writer import OutputWriter
from code.schemas import Action, MessageType
from code.utils.logger import setup_logger, get_logger
from code.utils.timer import timer

_logger = get_logger("main")

load_dotenv()

# ── Groq models ───────────────────────────────────────────────────────────────
ROUTING_MODEL    = "llama-3.3-70b-versatile"
VISION_MODEL     = "meta-llama/llama-4-scout-17b-16e-instruct"
TRANSCRIBE_MODEL = "whisper-large-v3"

# ── Deterministic rule engine ─────────────────────────────────────────────────

INJECTION_RE = re.compile(
    r"(ignore\s+(all\s+)?(previous|prior)\s+(rules?|instructions?|routing))"
    r"|(routing\s+override)"
    r"|(mark\s+(this\s+)?as\s+notify)"
    r"|(assistant\s+instruction)"
    r"|(set\s+action\s*=)"
    r"|(internal\s+router\s+metadata)"
    r"|(system\s+note\s+for\s+(the\s+)?notification\s+router)",
    re.IGNORECASE,
)
OTP_RE = re.compile(
    r"\b(otp|one[\s\-]time\s+pass(word|code)?|verification\s+code"
    r"|login\s+code|6[\s\-]digit\s+code)\b",
    re.IGNORECASE,
)
PHISH_RE = re.compile(
    r"\b(verify\s+(now|immediately|account|profile|wallet)"
    r"|account.{0,20}(block|suspend|restrict|lock)"
    r"|profile.{0,20}(block|suspend|restrict)"
    r"|share\s+(your\s+)?(otp|password|pin|account\s+number|bank\s+detail)"
    r"|send\s+(the\s+)?(code|otp|pin)"
    r"|confirm\s+(your\s+)?(otp|password|pin)"
    r"|reply\s+with\s+(the\s+)?(code|otp|6.digit)"
    r"|fill\s+bank\s+detail"
    r"|pay\s+(the\s+)?(clearance|reattempt|processing)\s+(amount|fee)"
    r"|scan\s+(this\s+)?qr\s+and\s+pay)\b",
    re.IGNORECASE,
)
CHAIN_RE = re.compile(
    r"\b(forward\s+(this|to\s+\d+\s+people)"
    r"|share\s+(with|to)\s+\d+"
    r"|don.t\s+(break|ignore)\s+the\s+chain"
    r"|send\s+to\s+(all|everyone|family\s+groups?)"
    r"|good\s+luck\s+(if\s+you\s+)?share"
    r"|luck\s+changes\s+when\s+you\s+share"
    r"|forward.{0,30}blessing)\b",
    re.IGNORECASE,
)
SUSP_DOMAIN_RE = re.compile(
    r"(account-login\.in|amazonpay-delivery\.in|account-help\.in"
    r"|pay-check-secure\.com|chase-secure-alert\.com"
    r"|bit\.ly/verify|profile-block|secure-alert)",
    re.IGNORECASE,
)


def _raw_value(row, col: str, default: str = "") -> str:
    """Safely read a value from a pd.Series row."""
    if col not in row.index:
        return default
    v = row[col]
    return "" if (v is None or str(v).strip() == "") else str(v).strip()


def apply_deterministic_rules(
    msg_row,        # raw pd.Series from messages.csv
    store,          # IndexStore
) -> Prediction | None:
    """
    Fast deterministic pre-filter.
    Returns a Prediction if a rule fires, else None → send to LLM.
    """
    text    = _raw_value(msg_row, "message_text")
    fwd     = int(_raw_value(msg_row, "forwarded_count") or "0")
    uid     = _raw_value(msg_row, "user_id")
    gid     = _raw_value(msg_row, "group_id")
    bid     = _raw_value(msg_row, "business_id")
    sid     = _raw_value(msg_row, "sender_user_id")
    mid     = _raw_value(msg_row, "message_id")

    def mute_pred(mtype: MessageType, reason: str, conf: float = 0.95) -> Prediction:
        return Prediction(
            message_id=mid,
            action=Action.MUTE,
            message_type=mtype,
            reason=reason,
            confidence=conf,
            evidence_message_ids=(),
        )

    # 1. Prompt injection
    if text and INJECTION_RE.search(text):
        return mute_pred(MessageType.SCAM,
            "Message contains a prompt injection attempt to override routing rules.",
            0.97)

    # 2. Known phishing domain
    if text and SUSP_DOMAIN_RE.search(text):
        return mute_pred(MessageType.SCAM,
            "Message contains a known phishing or spoofed domain.", 0.96)

    # 3. Business domain mismatch
    if bid:
        biz_row = store.businesses_by_id.get(bid)
        if biz_row is not None:
            official = _raw_value(biz_row, "official_domain")
            used     = _raw_value(biz_row, "domain_used_by_sender")
            verified = _raw_value(biz_row, "verified")
            reports  = int(_raw_value(biz_row, "user_reports_30d") or "0")
            if official and used and official != used:
                return mute_pred(MessageType.SCAM,
                    f"Business domain mismatch: official={official}, sender uses={used}.",
                    0.95)
            if verified == "0" and reports > 30:
                return mute_pred(MessageType.SPAM,
                    f"Unverified business with {reports} user reports in 30 days.",
                    0.90)

    # 4. OTP + account-block pressure
    if text and OTP_RE.search(text) and PHISH_RE.search(text):
        return mute_pred(MessageType.SCAM,
            "Message requests OTP or credentials with account-block pressure.", 0.95)

    # 5. Phishing language in forwarded message
    if text and PHISH_RE.search(text) and fwd >= 2:
        return mute_pred(MessageType.SCAM,
            "Forwarded message with payment or verification pressure; likely phishing.", 0.88)

    # 6. Chain/blessing with high forward count
    if fwd >= 6 and text and CHAIN_RE.search(text):
        # Gather evidence IDs from dismissed history
        evids = tuple(
            ev["message_id"] for ev_list in store.events_by_user.get(uid, [{}])
            if hasattr(ev_list, "get")
            for ev in [ev_list]
            if ev.get("notification_dismissed") == "1"
        )
        return Prediction(
            message_id=mid,
            action=Action.MUTE,
            message_type=MessageType.FORWARD,
            reason="High-forward-count chain/blessing message; user historically ignores these.",
            confidence=0.90,
            evidence_message_ids=evids,
        )

    # 7. Good-morning / blessing flood
    if fwd >= 8 and text:
        lower = text.lower()
        if any(kw in lower for kw in ["good morning", "bhagwan", "blessings",
                                       "positive energy", "stay blessed",
                                       "share this", "forwarding because",
                                       "share kar", "sabka bhala"]):
            return mute_pred(MessageType.GREETING,
                "High-forward-count morning/blessing message with no actionable content.",
                0.88)

    return None


# ── LLM helpers ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a WhatsApp message notification router. Decide how each message should be handled for the specific receiving user.

ACTIONS:
- notify  : interrupt the user now (time-sensitive, actionable, personal urgency)
- digest  : useful but not urgent; show in a later summary
- mute    : low-value, repetitive, unwanted promotional, or unsafe

MESSAGE TYPES (pick one):
personal, urgent, event, payment, business_update, promotion, greeting, forward, spam, scam, unknown

DECISION RULES (apply in order):

1. PROMOTIONS — strictly personalized
   - allows_promotions=0 OR promotions_opted_out_at is set → mute
   - High dismissal history for this business/sender → mute
   - User actively opted in and engaged → digest
   - Relevant to confirmed recent activity (active order, booked travel) → notify or digest

2. GROUP MESSAGES
   - group_muted_by_user=1 → mute/digest UNLESS user is @mentioned AND content is actionable
   - Group admin (role=admin) in society/school/coworker group sending operational update → notify
   - High dismissal rate in this group → prefer digest or mute

3. TIME-SENSITIVITY → notify
   - Same-day explicit deadline ("by 5 PM", "in 10 minutes", "before tonight")
   - Direct @mention with a clear ask from a trusted sender
   - Trusted contact needing an immediate decision

4. DO NOT DISTURB
   - Message during user's DND window → prefer digest unless medical/safety emergency

5. BUSINESS MESSAGES
   - Verified + domain match + active relationship → notify for transactional, digest for promotional
   - Verified + domain match + promotional + opted out → mute
   - Unknown sender, no relationship → digest if benign, mute if pushy

6. VOICE / IMAGE — use transcript/description to determine content, then apply same rules.

EVIDENCE: Cite specific historical message IDs (message_XXXX format). Use "none" only when no relevant history exists.

OUTPUT FORMAT: Valid JSON only. No markdown, no preamble.
{
  "action": "notify|digest|mute",
  "message_type": "personal|urgent|event|payment|business_update|promotion|greeting|forward|spam|scam|unknown",
  "reason": "1-2 sentence explanation",
  "confidence": 0.85,
  "evidence_message_ids": "message_0001;message_0002 or none"
}"""

VALID_ACTIONS = {a.value for a in Action}
VALID_TYPES   = {t.value for t in MessageType}


def _build_llm_prompt(context: MessageContext, store, media_note: str = "") -> str:
    """Build the structured routing prompt from a MessageContext."""
    msg = context.message
    s   = []

    # Core message fields
    s.append(
        f"=== INCOMING MESSAGE ===\n"
        f"id={msg.message_id}  user={msg.receiver_id}  "
        f"conv={msg.conversation_type.value}  fwd={getattr(msg, 'forwarded_count', 0)}"
    )
    if msg.content:
        s.append(f"\nMessage text:\n{msg.content}")
    if msg.media_type and msg.media_type.value != "text":
        s.append(f"Media type: {msg.media_type.value}")
    if media_note:
        s.append(f"Media content: {media_note}")

    # Receiver profile (raw row from store)
    user_row = store.users_by_id.get(msg.receiver_id)
    if user_row is not None:
        s.append(
            f"\n=== RECEIVER ===\n"
            f"DND={_raw_value(user_row,'do_not_disturb_window')}  "
            f"opened_30d={_raw_value(user_row,'messages_opened_30d')}  "
            f"replied_30d={_raw_value(user_row,'messages_replied_30d')}  "
            f"dismissed_30d={_raw_value(user_row,'notifications_dismissed_30d')}  "
            f"reported_30d={_raw_value(user_row,'messages_reported_30d')}"
        )

    # Group
    if msg.group_id:
        grp_row = store.groups_by_id.get(msg.group_id)
        if grp_row is not None:
            s.append(
                f"\n=== GROUP ===\n"
                f"name={_raw_value(grp_row,'group_name')}  "
                f"type={_raw_value(grp_row,'group_type')}  "
                f"size={_raw_value(grp_row,'member_count')}  "
                f"msgs_30d={_raw_value(grp_row,'messages_30d')}"
            )
        # User membership in this group
        for mem in store.members_by_group.get(msg.group_id, []):
            if _raw_value(mem, "user_id") == msg.receiver_id:
                s.append(
                    f"User membership: role={_raw_value(mem,'role')}  "
                    f"muted={_raw_value(mem,'group_muted_by_user')}  "
                    f"dismissed_30d={_raw_value(mem,'notifications_dismissed_30d')}  "
                    f"reads_30d={_raw_value(mem,'messages_read_30d')}  "
                    f"replies_30d={_raw_value(mem,'replies_sent_30d')}"
                )
                break
        # Sender role in group
        if msg.sender_id:
            for mem in store.members_by_group.get(msg.group_id, []):
                if _raw_value(mem, "user_id") == msg.sender_id:
                    s.append(f"Sender ({msg.sender_id}) role: {_raw_value(mem,'role')}")
                    break

    # Business
    if msg.business_id:
        biz_row = store.businesses_by_id.get(msg.business_id)
        if biz_row is not None:
            official = _raw_value(biz_row, "official_domain")
            used     = _raw_value(biz_row, "domain_used_by_sender")
            dmatch   = official == used and bool(official)
            s.append(
                f"\n=== BUSINESS ===\n"
                f"name={_raw_value(biz_row,'display_name')}  "
                f"cat={_raw_value(biz_row,'category')}  "
                f"verified={_raw_value(biz_row,'verified')}  "
                f"domain_match={dmatch}  "
                f"official={official}  sender_domain={used}  "
                f"acct_age={_raw_value(biz_row,'account_age_days')}d  "
                f"domain_age={_raw_value(biz_row,'domain_used_by_sender_age_days')}d  "
                f"reports_30d={_raw_value(biz_row,'user_reports_30d')}"
            )
        # User-business history
        for bh in store.business_history_by_user.get(msg.receiver_id, []):
            if _raw_value(bh, "business_id") == msg.business_id:
                s.append(
                    f"User↔Business: why={_raw_value(bh,'why_user_knows_account')}  "
                    f"allows_promo={_raw_value(bh,'allows_promotions')}  "
                    f"opted_out_at={_raw_value(bh,'promotions_opted_out_at')}  "
                    f"activity_180d={_raw_value(bh,'activity_count_180d')}  "
                    f"opened_30d={_raw_value(bh,'messages_opened_30d')}  "
                    f"dismissed_30d={_raw_value(bh,'messages_dismissed_30d')}"
                )
                break

    # Relevant history + events
    hist_rows = context.history
    if hist_rows:
        s.append("\n=== RELEVANT HISTORY + USER REACTIONS ===")
        ev_by_msg = {
            _raw_value(ev, "message_id"): ev
            for ev_list in [store.events_by_user.get(msg.receiver_id, [])]
            for ev in ev_list
        }
        ids = []
        for hm in hist_rows[:6]:
            h    = hm.message
            txt  = (h.content or "")[:80].replace("\n", " ")
            body = f'"{txt}"' if txt else f"[{h.media_type.value}]"
            ev   = ev_by_msg.get(h.message_id)
            if ev is not None:
                fl = []
                if _raw_value(ev, "message_opened")        == "1": fl.append("opened")
                if _raw_value(ev, "message_replied")        == "1": fl.append("replied")
                if _raw_value(ev, "notification_dismissed") == "1": fl.append("dismissed")
                if _raw_value(ev, "muted_after_message")    == "1": fl.append("muted-after")
                if _raw_value(ev, "message_reported")       == "1": fl.append("reported")
                rt  = _raw_value(ev, "reaction_time_minutes")
                rxn = (",".join(fl) if fl else "no-action") + (f" in {rt}m" if rt else "")
            else:
                rxn = "no-event"
            s.append(f"  [{h.message_id}] {body} → {rxn}")
            ids.append(h.message_id)
        if ids:
            s.append(f"Available evidence IDs: {', '.join(ids)}")
    else:
        s.append("\n=== RELEVANT HISTORY: none ===")

    s.append("\nReturn your JSON routing decision now.")
    return "\n".join(s)


def _encode_image(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode()


def _transcribe(audio_path: Path, client: Groq) -> str:
    try:
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                file=(audio_path.name, f),
                model=TRANSCRIBE_MODEL,
                response_format="text",
            )
        return str(result).strip()
    except Exception as exc:
        return f"[transcription failed: {exc}]"


def _describe_image(img_path: Path, client: Groq) -> str:
    try:
        b64 = _encode_image(img_path)
        resp = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text",
                     "text": ("Describe this WhatsApp message image in 2-3 sentences. "
                              "Focus on: message type (promotional poster, school notice, "
                              "document, scam alert, personal photo), key visible text, "
                              "urgency signals, and suspicious elements. Be factual.")}
                ],
            }],
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"[image analysis failed: {exc}]"


def _call_llm(prompt: str, client: Groq, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=ROUTING_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=350,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content.strip())
        except Exception as exc:
            if attempt == retries - 1:
                _logger.error("LLM failed after %d attempts: %s", retries, exc)
                return {}
            time.sleep(1.5)
    return {}


def _prediction_from_llm(message_id: str, raw: dict) -> Prediction:
    action_str = raw.get("action", "digest")
    type_str   = raw.get("message_type", "unknown")
    if action_str not in VALID_ACTIONS: action_str = "digest"
    if type_str   not in VALID_TYPES:   type_str   = "unknown"

    ev_raw = raw.get("evidence_message_ids", "none") or "none"
    ev_ids = () if ev_raw.strip() == "none" else tuple(
        e.strip() for e in ev_raw.replace("|", ";").split(";") if e.strip()
    )

    return Prediction(
        message_id=message_id,
        action=Action(action_str),
        message_type=MessageType(type_str),
        reason=str(raw.get("reason", "No reason provided.")),
        confidence=round(float(raw.get("confidence", 0.75)), 2),
        evidence_message_ids=ev_ids,
    )


# ── Pipeline wiring ───────────────────────────────────────────────────────────

def process_messages(
    indexer: MessageIndexer,
    context_builder: ContextBuilder,
    dataset,
    client: Groq,
    config: Config,
) -> list[Prediction]:
    """Route every message using deterministic rules first, LLM second."""
    store       = indexer.store
    predictions = []
    total       = len(indexer.all_messages)
    det_count   = 0

    # Build a raw-row index for messages.csv (needed for det_rules)
    raw_msg_by_id = {
        str(dataset.messages.iloc[i]["message_id"]): dataset.messages.iloc[i]
        for i in range(len(dataset.messages))
    }
    # Build image / voice note path indexes
    img_by_id = {
        str(dataset.images.iloc[i]["image_id"]): dataset.images.iloc[i]
        for i in range(len(dataset.images))
    }
    vn_by_id = {}
    if hasattr(dataset, "voice_notes") or "voice_notes.csv" in (dataset.additional or {}):
        vn_df = dataset.additional.get("voice_notes.csv") if dataset.additional else None
        if vn_df is not None:
            vn_by_id = {str(vn_df.iloc[i]["voice_note_id"]): vn_df.iloc[i]
                        for i in range(len(vn_df))}

    dataset_dir = config.data_dir.parent / "dataset"  # dataset/ sibling of data/ arg

    for i, message in enumerate(indexer.all_messages, 1):
        msg_row = raw_msg_by_id.get(message.message_id)
        tag     = "DET"
        pred    = None

        # ── Deterministic rules ──
        if config.enable_rule_engine and msg_row is not None:
            pred = apply_deterministic_rules(msg_row, store)
            if pred:
                det_count += 1
                tag = "DET"

        # ── LLM fallback ──
        if pred is None:
            tag     = "LLM"
            context = context_builder.build(message)

            media_note = ""
            if config.enable_media:
                media_id   = _raw_value(msg_row, "media_id")   if msg_row is not None else ""
                media_type = _raw_value(msg_row, "media_type") if msg_row is not None else ""

                if media_type == "voice" and media_id and media_id in vn_by_id:
                    fp = dataset_dir / "media" / _raw_value(vn_by_id[media_id], "file_path")
                    if fp.exists():
                        media_note = _transcribe(fp, client)

                elif media_type == "image" and media_id and media_id in img_by_id:
                    fp = dataset_dir / "media" / _raw_value(img_by_id[media_id], "file_path")
                    if fp.exists():
                        media_note = _describe_image(fp, client)

            prompt  = _build_llm_prompt(context, store, media_note)
            raw_out = _call_llm(prompt, client, retries=config.max_llm_retries)
            pred    = _prediction_from_llm(message.message_id, raw_out)
            time.sleep(0.2)

        _logger.info(
            "[%3d/%d] [%s] %-10s → %-6s %-18s conf=%.2f",
            i, total, tag, message.message_id,
            pred.action.value, pred.message_type.value, pred.confidence,
        )
        predictions.append(pred)

    _logger.info(
        "Routing complete — notify=%d digest=%d mute=%d (det=%d llm=%d)",
        sum(1 for p in predictions if p.action == Action.NOTIFY),
        sum(1 for p in predictions if p.action == Action.DIGEST),
        sum(1 for p in predictions if p.action == Action.MUTE),
        det_count, total - det_count,
    )
    return predictions


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-powered WhatsApp Message Notification Router",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=Path("dataset"),
        help="Directory containing input CSV datasets (default: dataset/)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("dataset/output.csv"),
        help="Output CSV file path (default: dataset/output.csv)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        help="Logging level: DEBUG, INFO, WARNING, ERROR",
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args   = parse_args()
    config = load_config(data_dir=args.data_dir, output_path=args.output)
    logger = setup_logger(level=args.log_level, log_file=config.log_file)
    logger.info("Starting WhatsApp Message Notification Router")

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        logger.error("GROQ_API_KEY is not set in environment.")
        return 1

    client = Groq(api_key=api_key)

    try:
        with timer("pipeline"):
            # Load
            loader  = DatasetLoader(config.data_dir)
            dataset = loader.load()
            logger.info("Loaded %d messages", len(dataset.messages))

            # Index
            indexer = MessageIndexer()
            indexer.build(dataset)

            # Context builder
            context_builder = ContextBuilder(indexer, config)

            # Route
            predictions = process_messages(
                indexer, context_builder, dataset, client, config,
            )

            # Write
            writer = OutputWriter(config.output_path)
            writer.write(predictions)

        logger.info("Pipeline completed successfully")
        return 0

    except Exception:
        logger.exception("Pipeline failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())