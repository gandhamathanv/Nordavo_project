"""Deterministic safety checks that run without an LLM.

- normalise_text():    NFKC + no invisible characters, so every regex below sees what a human reader sees.
- redact():            removes payment details before text reaches the LLM, a log line or the helpdesk.
- injection_signals(): spots text that tries to instruct an AI ("ignore previous instructions", ...).
- rule_keyword_hits(): a keyword safety net for the client's always-a-human rules, in nl/en/de.
- foreign_contact_details() / reply_commitments(): what a drafted reply may not contain: links, addresses and
                       numbers the help centre does not give, and promises (refund, discount, call-back, deadline).
                       It can only ever force a handoff, so a false positive costs a human a minute,
                       while a false negative is still caught by the LLM's own rule_triggers.
- detect_language():   stopword vote between nl/en/de, used to check the language of a draft reply.
"""

from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------- normalisation

# Zero-width, soft-hyphen and bidi-format characters: "4111<ZWSP>1111" and "ig<ZWSP>nore" read normally to a person.
_INVISIBLE = re.compile("[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")


def normalise_text(text: str) -> str:
    """NFKC (fullwidth letters and digits, no-break spaces and ligatures become plain ones) without invisible
    characters. Every guard below works on this, so formatting tricks cannot hide data from a regex."""
    return _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))


# --------------------------------------------------------------------------- payment details

_CARD = re.compile(r"(?<![\d€.,])(?:\d[ -]?){12,18}\d(?![\d])")
# Four groups of four digits that may also be split by dots, tabs or line breaks: "4111.1111.1111.1111".
_CARD_GROUPED = re.compile(r"(?<![\d€.,])\d{4}(?:[\s.\-]{1,2}\d{4}){3}(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[ .-]?(?:[A-Z0-9]{4}[ .-]?){2,7}[A-Z0-9]{1,4}\b", re.I)
_CVC = re.compile(
    r"\b(?:cvc2?|cvv2?|cid|csc|security\s+code|verification\s+(?:code|number)|beveiligingscode|veiligheidscode|"
    r"kaartcode|pr[üu]fnummer|kartenpr[üu]fnummer|sicherheitscode|pin(?:code)?)"
    r"(?:[\s-]*(?:code|number|nummer))?\s*[:=]?\s*\d{3,4}\b",
    re.I,
)
_EXPIRY = re.compile(
    r"\b(?:geldig tot|vervaldatum|verloopt|exp(?:ir(?:es|e|y|ation))?(?: date)?|valid (?:until|thru)|gültig bis)\b\s*[:]?\s*\d{1,2}\s*/\s*\d{2,4}",
    re.I,
)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def redact(text: str) -> tuple[str, list[str]]:
    """Return (text without payment details, kinds of data removed).

    Any 13-19 digit run is removed, Luhn-valid or not: a mistyped card number is still a card number.
    The returned text is the normalised one (see normalise_text).
    """
    text = normalise_text(text)
    kinds: list[str] = []

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        kinds.append("card_number" if _luhn_ok(digits) else "long_number")
        return "[REDACTED NUMBER]"

    def tag(kind: str, label: str):
        def _sub(_m: re.Match) -> str:
            kinds.append(kind)
            return label
        return _sub

    text = _IBAN.sub(tag("iban", "[REDACTED IBAN]"), text)
    text = _CVC.sub(tag("cvc", "[REDACTED CVC]"), text)
    text = _EXPIRY.sub(tag("card_expiry", "[REDACTED EXPIRY]"), text)
    text = _CARD_GROUPED.sub(card, text)
    text = _CARD.sub(card, text)
    return text, kinds


def contains_payment_details(text: str) -> bool:
    return bool(redact(text)[1])


# --------------------------------------------------------------------------- prompt injection

_INJECTION = [
    r"negeer\s+(?:alle\s+)?(?:eerdere|vorige|voorgaande|bovenstaande)\s+(?:instructies|opdrachten|regels)",
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts|rules)",
    r"ignorier(?:e|en)?\s+(?:alle\s+)?(?:vorherigen|bisherigen|obigen)\s+(?:anweisungen|instruktionen|regeln)",
    r"\b(?:systeembericht|system\s*message|system\s*prompt|systemnachricht)\b",
    r"\b(?:ai|ki)[- ]?(?:assistent|assistant|agent)\b",
    r"\bnotitie\s+voor\s+de\s+(?:ai|bot|assistent)",
    r"\b(?:you are now|je bent nu|du bist jetzt)\b",
    r"\b(?:zet|set|change)\s+(?:de\s+|the\s+)?priori(?:teit|ty)\s+(?:op|to)\b",
]
_INJECTION_RE = re.compile("|".join(_INJECTION), re.I)


def injection_signals(text: str) -> list[str]:
    return [m.group(0) for m in _INJECTION_RE.finditer(normalise_text(text))]


# --------------------------------------------------------------------------- client rules

RULE_KEYWORDS: dict[str, list[str]] = {
    "refund_or_dispute": [
        r"terugbetal", r"terugstort", r"terugkrijg", r"geld\s+terug", r"restitut", r"dubbel\s+afgeschreven",
        r"twee\s+keer\s+.{0,20}afgeschreven", r"\brefund", r"money\s+back", r"charge\s*back", r"charged\s+twice",
        r"rückerstatt", r"geld\s+zurück", r"doppelt\s+abgebucht",
    ],
    "cancellation_or_contract": [
        r"\bopzeg", r"zeggen\s+(?:we|wij|ik)\s+.{0,20}op\b", r"abonnement\s+.{0,20}beëindig",
        r"cancel(?:l?ing)?\s+(?:my|our|the)\s+(?:subscription|account|contract|plan)", r"\bcancellation\b",
        r"terminate\s+(?:my|our|the)\s+(?:subscription|contract)", r"\bkündig",
    ],
    "gdpr": [
        r"\bavg\b", r"\bgdpr\b", r"\bdsgvo\b", r"persoonsgegevens", r"persoonlijke\s+gegevens", r"inzageverzoek",
        r"recht\s+op\s+(?:inzage|vergetelheid)", r"gegevens\s+.{0,40}verwijder", r"personal\s+data",
        r"delete\s+(?:all\s+)?my\s+data", r"right\s+to\s+be\s+forgotten", r"personenbezogene", r"daten\s+löschen",
    ],
    "security": [
        r"gehackt", r"\bhacked\b", r"phishing", r"datalek", r"data\s+breach", r"(?:vreemde|onbekende|verdachte)\s+(?:login|inlog)",
        r"heeft\s+ingelogd", r"ingelogd\s+vanuit", r"dat\s+waren\s+wij\s+niet", r"logged\s+in\s+from",
        r"unauthori[sz]ed\s+(?:access|login)", r"that\s+wasn'?t\s+(?:us|me)", r"unbefugt", r"das\s+waren\s+wir\s+nicht",
    ],
    "legal": [
        r"advocaat", r"\bjurist", r"rechtszaak", r"juridische\s+stappen", r"schadevergoeding", r"aansprakelijk",
        r"ingebrekestelling", r"\blawyer", r"attorney", r"lawsuit", r"legal\s+action", r"\bsue\b", r"anwalt",
        r"\bklage\b", r"schadensersatz",
    ],
    "churn_threat": [
        r"zeggen\s+(?:we|wij|ik)\s+.{0,20}op\b", r"overstappen\s+naar", r"stappen\s+.{0,20}over\s+naar",
        r"andere\s+(?:leverancier|aanbieder|app)", r"switch(?:ing)?\s+to\s+(?:another|a\s+competitor)",
        r"we\s*(?:'re|\s+are)\s+leaving", r"anbieter\s+wechseln",
    ],
}
_RULE_RES = {rule: re.compile("|".join(pats), re.I) for rule, pats in RULE_KEYWORDS.items()}


def rule_keyword_hits(text: str) -> list[str]:
    text = normalise_text(text)
    return [rule for rule, rx in _RULE_RES.items() if rx.search(text)]


# --------------------------------------------------------------------------- what a reply may contain

# Contact details: any link with a scheme or "www.", mailto/tel/javascript links, e-mail addresses, phone numbers,
# and bare host names that end in a common top-level domain. A reply may only repeat the ones in the help-centre
# sections it cites, so a steered drafter cannot slip a phishing link or a made-up number into a customer message.
_LINK = re.compile(r"\b(?:https?://|www\.)[^\s<>()\[\]\"']+|\b(?:mailto|tel|javascript):[^\s<>()\[\]\"']+", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Top-level domains only if they are not also everyday words ("de", "be", "me", "us", "ga", "co" are left out, so a
# sentence like "...groet.De Team" is not mistaken for a host). Links with a scheme or "www." are caught anyway.
_TLDS = ("nl|com|eu|org|net|io|app|dev|info|biz|uk|fr|ru|cn|xyz|top|online|site|shop|link|click|tk|ml|cf|gq|example")
_HOST = re.compile(rf"\b(?:[a-z0-9-]+\.)+(?:{_TLDS})\b(?:/[^\s<>()\[\]\"']*)?", re.I)
_PHONE = re.compile(r"(?<![\w.])\+?\d(?:[\s().-]?\d){8,}(?!\w)")


def _contact_key(token: str) -> str:
    token = token.lower().rstrip(".,;:!?)]'\"")
    return re.sub(r"^(?:https?://)?(?:www\.)?", "", token).rstrip("/")


def contact_details(text: str) -> set[str]:
    """Links, addresses, hosts and phone numbers in `text`, lower-cased, without scheme or trailing punctuation."""
    text = normalise_text(text)
    return {key for rx in (_LINK, _EMAIL, _HOST, _PHONE) for m in rx.finditer(text) if (key := _contact_key(m.group(0)))}


def foreign_contact_details(text: str, allowed: set[str]) -> list[str]:
    """Contact details in `text` that are not in `allowed`. A host is fine when it is the start of an allowed link
    ("app.roosterly.nl" for "app.roosterly.nl/login"); a longer path than the allowed one is not."""
    return sorted(t for t in contact_details(text) if not any(a == t or a.startswith(t + "/") for a in allowed))


# Commitments the support team must never make in an automatic reply (client rule: refunds, cancellations and
# contract changes go to a human). Deliberately narrow: words that also appear in negations ("we cannot promise")
# or in help-centre facts ("within 10 minutes") are not listed.
_COMMITMENT = re.compile("|".join([
    # refunds and money back
    r"\brefund", r"\bterugbetal", r"\bterugstort", r"\bterugboek", r"\bcreditnota\b", r"\berstatt", r"\bzurückzahl",
    r"\b(?:storten|betalen|boeken|maken)\b[^.!?]{0,60}\bterug\b",
    r"\b(?:pay|send|give)\b[^.!?]{0,30}\bback\b",
    # discounts, credit, compensation, free things
    r"\bgratis\b", r"\bkorting\b", r"\btegoed\b", r"\bcompensatie\b", r"\bkwijtschelding\b",
    r"\bfree\s+of\s+charge\b", r"\bfor\s+free\b", r"\bdiscount", r"\bcredit(?:ed)?\b(?!\s+card)", r"\bcompensat",
    r"\bkostenlos\b", r"\brabatt", r"\bgutschrift", r"\bentschädigung",
    # call-backs and deadlines
    r"\bterugbel", r"\b(?:we|wij)\s+bellen\b", r"\bcall\s+you\s+back\b", r"\bwe(?:'ll|\s+will)\s+call\b",
    r"\brückruf", r"\bwir\s+rufen\b",
    r"\bbinnen\s+(?:\d+|een|één|twee|drie|vier|vijf)\s+(?:werk)?(?:uur|uren|dag|dagen|week|weken)\b",
    r"\bwithin\s+(?:\d+|an?|one|two|three|four|five)\s+(?:business\s+|working\s+)?(?:hours?|days?|weeks?)\b",
    r"\binnerhalb\s+(?:von\s+)?(?:\d+|einer|einem|zwei|drei|vier|fünf)\s+(?:Stunden?|Tagen?|Wochen?)\b",
    # something was done to the account
    r"\bis\s+(?:per\s+direct\s+)?opgezegd\b", r"\bhas\s+been\s+(?:cancell?ed|terminated|refunded)\b",
    r"\b(?:wurde|ist)\s+gekündigt\b",
]), re.I)


def reply_commitments(text: str) -> list[str]:
    return [m.group(0) for m in _COMMITMENT.finditer(normalise_text(text))]


# --------------------------------------------------------------------------- language

_STOPWORDS = {
    "nl": set("""de het een en is ik je jij jullie we wij niet van op voor met dat die er ons onze mijn hoe wat
        waar kan kunnen graag naar bij ook zijn heb hebben wordt worden deze dit u uw als maar dan nog geen om aan
        te tot door over hoi groet vriendelijke ga gaat kun kunt vind vindt staat staan zo even""".split()),
    "en": set("""the a an and is are i you we our my not of on for with that this it can how what where to in
        from be have has your please would there do does when if but no at by as us hi thanks regards go find
        you'll will you're""".split()),
    "de": set("""der die das und ist ich sie wir nicht von auf für mit dass es ein eine kann können wie was wo
        zu im den dem des auch haben hat sind ihre ihr unsere bitte gibt sich bei aus noch nur mein meine uns
        hallo grüße freundlichen gehen sie finden unter""".split()),
}
# Words that exist in more than one of the languages ("we", "in", "die", "is", ...) carry no signal: drop them.
_SHARED = {w for lang, ws in _STOPWORDS.items() for other, os_ in _STOPWORDS.items() if lang != other for w in ws & os_}
_STOPWORDS = {lang: ws - _SHARED for lang, ws in _STOPWORDS.items()}
_WORD = re.compile(r"[a-zäöüßéëï']+")


def detect_language(text: str) -> tuple[str | None, dict[str, int]]:
    """Return (language or None if unclear, stopword hits per language)."""
    words = _WORD.findall(text.lower())
    scores = {lang: sum(w in sw for w in words) for lang, sw in _STOPWORDS.items()}
    scores["de"] += 2 * len(re.findall(r"[äöüß]", text.lower()))
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, top), (_, second) = ranked[0], ranked[1]
    if top < 2 or top - second < 2:
        return None, scores
    return best, scores
