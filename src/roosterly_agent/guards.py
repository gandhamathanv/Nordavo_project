"""Deterministic safety checks that run without an LLM.

- redact():            removes payment details before text reaches the LLM, a log line or the helpdesk.
- injection_signals(): spots text that tries to instruct an AI ("ignore previous instructions", ...).
- rule_keyword_hits(): a keyword safety net for the client's always-a-human rules, in nl/en/de.
                       It can only ever force a handoff, so a false positive costs a human a minute,
                       while a false negative is still caught by the LLM's own rule_triggers.
- detect_language():   stopword vote between nl/en/de, used to check the language of a draft reply.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- payment details

_CARD = re.compile(r"(?<![\d€.,])(?:\d[ -]?){12,18}\d(?![\d])")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[ ]?(?:[A-Za-z0-9]{4}[ ]?){2,7}[A-Za-z0-9]{1,4}\b")
_CVC = re.compile(r"\b(?:cvc|cvv2?|cid|csc|beveiligingscode|kaartcode|prüfnummer|sicherheitscode)\b\s*[:=]?\s*\d{3,4}\b", re.I)
_EXPIRY = re.compile(
    r"\b(?:geldig tot|vervaldatum|verloopt|exp(?:iry|iration)?(?: date)?|valid (?:until|thru)|gültig bis)\b\s*[:]?\s*\d{1,2}\s*/\s*\d{2,4}",
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
    """
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
    return [m.group(0) for m in _INJECTION_RE.finditer(text)]


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
    return [rule for rule, rx in _RULE_RES.items() if rx.search(text)]


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
