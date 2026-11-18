"""Reply quality, found by comparing the app with Nordavo's 10 labelled examples: an English word left inside a Dutch
sentence (E04: "Colleagues met dezelfde rol...") and a missing total (E07: price for 25 employees)."""

import pytest

from roosterly_agent import prompts
from roosterly_agent.faq import english_leftovers
from roosterly_agent.pipeline import Pipeline
from security_helpers import FAQ, GOOD_REPLY_NL, ScriptedLLM, make_draft, make_ticket, make_triage, make_verification

E04_REPLY = ('Beste klant, medewerkers openen de dienst in de app en tikken op "Ruil aanbieden". Colleagues met dezelfde '
             "rol kunnen de ruil accepteren. De manager keurt dit goed via Rooster → Verzoeken. Met vriendelijke groet, Team Roosterly")
E04_FIXED = E04_REPLY.replace("Colleagues", "Collega's")
F03 = dict(questions=[__import__("roosterly_agent.schemas", fromlist=["Question"]).Question(
    question_en="How do I swap a shift?", faq_ids=["F03"], covered_by_faq=True)])
BODY = "Hoe ruil ik een dienst met een collega? Kunnen jullie dat uitleggen, graag."


def run(llm):
    return Pipeline(FAQ, llm).decide(make_ticket(body=BODY))


# ------------------------------------------------------------------ the detector

def test_the_english_word_from_example_e04_is_found():
    assert english_leftovers(E04_REPLY, FAQ, ["F03"], "nl") == ["colleagues"]
    assert english_leftovers(E04_FIXED, FAQ, ["F03"], "nl") == []


@pytest.mark.parametrize("reply,ids,lang", [
    (E04_FIXED, ["F03"], "nl"),
    ("Hallo. Jeder Benutzer wählt seine Sprache unter Profiel → Taal (Profile → Language). Mit freundlichen Grüßen", ["F08"], "de"),
    ('Klik op "Ruil aanbieden" (Offer swap) en wacht op de manager.', ["F03"], "nl"),
    ("De data staat in de EU, zie de verwerkersovereenkomst. Mail naar de manager.", ["F09"], "nl"),
    ("Bekijk de actuele storingen op status.roosterly.nl en onze openbare roadmap op roadmap.roosterly.nl.", ["F11", "F10"], "nl"),
    ("Plus kost €6 per actieve medewerker per maand, exclusief btw. Upgraden kan onder Instellingen → Abonnement.", ["F05"], "nl"),
    ("Employees open the shift. Colleagues with the same role can accept.", ["F03"], "en"),       # English reply: nothing to flag
])
def test_good_replies_have_no_english_leftovers(reply, ids, lang):
    assert english_leftovers(reply, FAQ, ids, lang) == []


# ------------------------------------------------------------------ the pipeline

def test_an_english_leftover_triggers_one_redraft_without_an_extra_review():
    llm = ScriptedLLM(make_triage(**F03), draft=make_draft(E04_REPLY, ids=["F03"]), redraft=make_draft(E04_FIXED, ids=["F03"]),
                      verification=make_verification())
    d = run(llm)
    assert d.action == "reply" and d.payload["draft_reply"] == E04_FIXED and "redrafted_for_english_words" in d.flags
    assert llm.purposes == ["triage", "draft", "redraft", "verify"]
    assert "colleagues" in llm.calls[2]["user"] and "translate every word" in llm.calls[2]["user"]


def test_still_an_english_leftover_after_the_redraft_goes_to_a_human():
    llm = ScriptedLLM(make_triage(**F03), draft=make_draft(E04_REPLY, ids=["F03"]), redraft=make_draft(E04_REPLY, ids=["F03"]),
                      verification=make_verification())
    d = run(llm)
    assert d.action == "handoff" and "English words left in the reply: colleagues" in d.payload["handoff_note"]
    assert llm.purposes == ["triage", "draft", "redraft", "verify"]            # one redraft, never a loop


def test_a_clean_reply_costs_no_extra_call():
    llm = ScriptedLLM(make_triage(), draft=make_draft(), verification=make_verification())
    d = Pipeline(FAQ, llm).decide(make_ticket())
    assert d.action == "reply" and llm.purposes == ["triage", "draft", "verify"] and d.checks["english_leftovers"] == []


# ------------------------------------------------------------------ the prompts

def test_the_prompts_ask_for_full_translation_and_for_totals():
    draft = prompts.draft_system(FAQ, ["F05"], "nl")
    assert "Translate every ordinary word" in draft and "show the calculation" in draft
    assert "25 x" not in draft                                    # the example must not be a label's answer
    assert "product names (Roosterly" not in draft                # naming Roosterly there made the drafter write "Roosterly works on iOS 16"
    assert "Arithmetic" in prompts.verify_system(FAQ, ["F05"], "nl")
