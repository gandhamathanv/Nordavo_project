# Eval: postfix

Model `gemini-3.5-flash-lite`, 2026-11-18T14:42:26+00:00.

| metric | nordavo (10 labelled examples) | extra (hand-labelled) |
|---|---|---|
| action_accuracy | 10/10 (100%) | 8/8 (100%) |
| category_accuracy | 10/10 (100%) | 8/8 (100%) |
| priority_accuracy | 10/10 (100%) | 6/6 (100%) |
| language_accuracy | 10/10 (100%) | 8/8 (100%) |
| all_scored_fields_correct | 10/10 (100%) | 8/8 (100%) |
| unsafe_decisions | 0 | 0 |
| over_escalations | 0 | 0 |
| expected_replies_sent | 6/6 (100%) | 5/5 (100%) |
| reply_faq_match | 6/6 (100%) | 5/5 (100%) |
| reply_language_ok | 6/6 (100%) | 5/5 (100%) |
| errors | 0 | 0 |

Tokens per ticket: {'input_tokens': 2262, 'output_tokens': 353, 'thinking_tokens': 0}, LLM calls per ticket: 2.22, cost per 100 tickets (paid tier): $0.1561

| id | gold (action / cat / prio / lang) | predicted | wrong fields | notes |
|---|---|---|---|---|
| E01 | reply / bug / P3 / en | reply / bug / P3 / en | - |  |
| E02 | reply / billing / P4 / nl | reply / billing / P4 / nl | - |  |
| E03 | handoff / billing / P2 / nl | handoff / billing / P2 / nl | - |  |
| E04 | reply / question / P4 / nl | reply / question / P4 / nl | - |  |
| E05 | reply / feature_request / P4 / nl | reply / feature_request / P4 / nl | - |  |
| E06 | handoff / bug / P2 / en | handoff / bug / P2 / en | - |  |
| E07 | reply / billing / P4 / nl | reply / billing / P4 / nl | - |  |
| E08 | close / other / P4 / nl | close / other / P4 / nl | - |  |
| E09 | handoff / other / P2 / nl | handoff / other / P2 / nl | - |  |
| E10 | reply / question / P4 / nl | reply / question / P4 / nl | - |  |
| X01 | handoff / bug / P1 / en | handoff / bug / P1 / en | - |  |
| X02 | reply / billing / P4 / en | reply / billing / P4 / en | - |  |
| X03 | reply / question / P4 / en | reply / question / P4 / en | - |  |
| X04 | reply / question / P4 / nl | reply / question / P4 / nl | - |  |
| X05 | handoff / bug / None / de | handoff / bug / P2 / de | - |  |
| X06 | handoff / bug / P4 / en | handoff / bug / P4 / en | - |  |
| X07 | reply / question / P4 / nl | reply / question / P4 / nl | - |  |
| X08 | reply / question / None / en | reply / question / P3 / en | - |  |

## Per ticket

### E01: App crashes

- Ticket: The app crashes immediately on my iPhone 8 (iOS 15). Other staff are fine.
- Gold reason: English ticket. FAQ F12 covers it: the app needs iOS 16 or later, so we can answer in English without a human.
- Agent reason: One customer is blocked by an app crash, but there is a clear cause covered in the help centre (P3). Reply: answered by help centre F12.
- Reply sent: 'Hello, the app works on iOS 16 and later and Android 10 and later. Kind regards, Team Roosterly'
- Back-translation (EN): Hello, the app works on iOS 16 and later and Android 10 and later. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['iOS 16', 'Android 10']

### E02: Btw-nummer

- Ticket: Ons btw-nummer is veranderd. Kunnen jullie het nieuwe op onze facturen zetten?
- Gold reason: How to change invoice details is in FAQ F06. Reply in Dutch.
- Agent reason: This is a standard administrative question about how-to procedures (P4). Reply: answered by help centre F06.
- Reply sent: 'Beste klant, je kunt het btw-nummer voor toekomstige facturen wijzigen onder Instellingen → Bedrijfsgegevens. Vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, you can change the VAT number for future invoices under Instellingen -> Bedrijfsgegevens. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Bedrijfsgegevens']

### E03: Terugbetaling

- Ticket: We waren in augustus dicht wegens verbouwing. Kunnen we die maand terugkrijgen?
- Gold reason: Refund request ('terugkrijgen' = get back). Client rule: refunds always go to a human.
- Agent reason: Money or the contract is involved via a refund request (P2). Handoff: client rule, refunds and disputed charges always go to a human.
- Handoff note: The customer is requesting a refund for August because their restaurant was closed for renovations. Since refund requests must always go to a human, a support agent needs to handle this case. Client rule: refund_or_dispute.

### E04: Dienst ruilen

- Ticket: Hoe ruil ik een dienst met een collega?
- Gold reason: Dutch how-to question about swapping shifts, answered by FAQ F03. Reply in Dutch.
- Agent reason: This is a standard how-to question with no urgency or blockage (P4). Reply: answered by help centre F03.
- Reply sent: 'Beste klant, medewerkers openen de dienst in de app en tikken op "Ruil aanbieden". Colleagues met dezelfde rol kunnen de ruil accepteren. De manager keurt dit goed via Rooster → Verzoeken. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, employees open the shift in the app and tap "Ruil aanbieden". Colleagues with the same role can accept the swap. The manager approves this via Rooster → Verzoeken. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Rooster → Verzoeken', 'Ruil aanbieden']

### E05: Google Agenda

- Ticket: Graag een koppeling met Google Agenda voor de diensten.
- Gold reason: Feature request (Google Calendar sync). Acknowledge in Dutch and point to the roadmap (F10).
- Agent reason: This is a feature request with no urgency (P4). Reply: answered by help centre F10.
- Reply sent: 'Beste klant, bedankt voor je idee voor Roosterly. Wij lezen elk idee en functieverzoeken gaan naar onze openbare roadmap op roadmap.roosterly.nl, waar je op ideeën kunt stemmen. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, thank you for your idea for Roosterly. We read every idea and feature requests go to our public roadmap at roadmap.roosterly.nl, where you can vote on ideas. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['roadmap.roosterly.nl']

### E06: Can't publish rota

- Ticket: When I click Publish I get 'Something went wrong'. Next week's rota is not visible for staff.
- Gold reason: One customer blocked from publishing: P2, needs an engineer.
- Agent reason: One customer is blocked from publishing their rota, impacting staff visibility for next week (P2). Handoff: not covered by the help centre: Why do I get 'Something went wrong' when clicking Publish and how can I fix it?.
- Handoff note: The customer is experiencing a 'Something went wrong' error when trying to publish next week's rota. A human support agent needs to investigate the publishing failure.

### E07: Prijs Plus

- Ticket: Wat kost Plus voor 25 medewerkers?
- Gold reason: Price question answered by F05 (25 x €6 = €150 excl. VAT). Reply in Dutch.
- Agent reason: It is a standard pricing and information question with no urgency (P4). Reply: answered by help centre F05.
- Reply sent: 'Beste klant, Plus kost €6 per actieve medewerker per maand exclusief btw. Je kunt op elk moment upgraden via Instellingen → Abonnement, waarna de nieuwe prijs geldt vanaf de volgende factuur. Groeten, Team Roosterly'
- Back-translation (EN): Dear customer, Plus costs €6 per active employee per month excluding VAT. You can upgrade at any time via Settings → Subscription, after which the new price applies from the next invoice. Regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Abonnement', '€6']

### E08: Investeringskans

- Ticket: Verdubbel je geld in 7 dagen met ons cryptofonds.
- Gold reason: Spam (crypto offer): close it.
- Agent reason: The message is spam and requires no customer support action (P4). Close: spam, not a customer request.

### E09: Inzageverzoek

- Ticket: Ik wil graag inzage in alle persoonsgegevens die jullie over mij bewaren (AVG).
- Gold reason: GDPR access request ('inzageverzoek', AVG = Dutch GDPR): always a human.
- Agent reason: Personal data requests under GDPR require handling by a human support agent (P2). Handoff: client rule, personal data (GDPR/AVG) requests always go to a human.
- Handoff note: The customer is making a personal data access request under GDPR (AVG). A human agent must process this request according to company data privacy procedures. Client rule: gdpr.

### E10: Onderhoud

- Ticket: Is er vanavond onderhoud gepland?
- Gold reason: Asks about planned maintenance tonight. Point to the status page (F11), in Dutch.
- Agent reason: This is a simple informational question about system maintenance (P4). Reply: answered by help centre F11.
- Reply sent: 'Beste klant, je kunt status.roosterly.nl bekijken voor actuele storingen en gepland onderhoud. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, you can check status.roosterly.nl for current outages and planned maintenance. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['status.roosterly.nl']

### X01: URGENT clock-in broken

- Ticket: URGENT: since 07:30 none of the staff in our two cafés in Utrecht can clock in. The app just shows a spinning wheel. Breakfast service starts at 8.
- Gold reason: English. Many users blocked right now: P1, needs a human.
- Agent reason: Multiple users across multiple locations are currently blocked from clocking in during service hours (P1). Handoff: P1, needs a human right away.
- Handoff note: Urgent bug report from a Plus plan customer regarding clock-in failure across two locations affecting breakfast service. Check status.roosterly.nl and investigate immediately.

### X02: Invoice

- Ticket: Hi, quick one: where do I download last month's invoice? Our bookkeeper in Zwolle needs it. Thanks, Pieter
- Gold reason: English how-to, answered by F06.
- Agent reason: It is a standard how-to question about billing with no urgency (P4). Reply: answered by help centre F06.
- Reply sent: 'Hi Pieter. Invoices are emailed on the 1st of every month and you can download them under Instellingen → Abonnement → Facturen (Settings → Subscription → Invoices). Best regards, Team Roosterly'
- Back-translation (EN): Hi Pieter. Invoices are emailed on the 1st of every month and you can download them under Instellingen → Abonnement → Facturen (Settings → Subscription → Invoices). Best regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Abonnement → Facturen']

### X03: AFAS

- Ticket: We have the Basis plan. Can Roosterly send our approved hours to AFAS?
- Gold reason: English. F04 answers it: AFAS export exists and is part of the Plus plan.
- Agent reason: This is a straightforward how-to or feature availability question with no urgency (P4). Reply: answered by help centre F04.
- Reply sent: 'Hello. Roosterly exports approved hours to Nmbrs, Loket.nl and AFAS, or as a CSV file. You can set this up under Instellingen → Koppelingen → Salaris (Settings → Integrations → Payroll). The AFAS integration is part of the Plus plan. Best regards, Team Roosterly'
- Back-translation (EN): Hello. Roosterly exports approved hours to Nmbrs, Loket.nl and AFAS, or as a CSV file. You can set this up under Instellingen → Koppelingen → Salaris (Settings → Integrations → Payroll). The AFAS integration is part of the Plus plan. Best regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Koppelingen → Salaris', 'Loket.nl', 'AFAS', 'CSV']

### X04: Uren naar AFAS

- Ticket: Kan Roosterly onze goedgekeurde uren naar AFAS sturen? We hebben Basis.
- English gloss: Can Roosterly send our approved hours to AFAS? We have Basis.
- Gold reason: Dutch. F04 answers it: AFAS export exists and is part of the Plus plan.
- Agent reason: It is a standard how-to and feature availability question with no urgency (P4). Reply: answered by help centre F04.
- Reply sent: 'Beste klant, Roosterly exporteert goedgekeurde uren naar Nmbrs, Loket.nl en AFAS, of als een CSV-bestand. De integraties met Nmbrs, Loket.nl en AFAS maken deel uit van het Plus-abonnement. Je stelt dit in onder Instellingen → Koppelingen → Salaris. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, Roosterly exports approved hours to Nmbrs, Loket.nl and AFAS, or as a CSV file. The integrations with Nmbrs, Loket.nl and AFAS are part of the Plus plan. You set this up under Settings → Integrations → Payroll. Sincerely, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Koppelingen → Salaris', 'Loket.nl', 'AFAS', 'CSV']

### X05: Falsche Schichten

- Ticket: Seit heute Morgen zeigt die App bei allen Mitarbeitern in Venlo falsche Schichten an. Bitte dringend prüfen.
- English gloss: Since this morning the app shows wrong shifts for all employees in Venlo. Please check urgently.
- Gold reason: German bug report not covered by the FAQ: human.
- Agent reason: Multiple employees are currently affected by incorrect schedule data at a specific location (P2). Handoff: not covered by the help centre: Why are incorrect shifts being displayed for all employees in Venlo since this morning?.
- Handoff note: The customer on the Plus plan reports incorrect shift displays for all staff at the Venlo location. Please investigate the scheduling data issue immediately.

### X06: Untranslated button

- Ticket: The Dutch word 'Uitnodigen' on the invite button is not translated in the English app. Minor thing.
- Gold reason: English cosmetic bug, not in the FAQ: human, no urgency.
- Agent reason: It is a minor cosmetic issue with no user blockage (P4). Handoff: not covered by the help centre: Why is the 'Uitnodigen' button not translated in the English app?.
- Handoff note: Customer reports an untranslated button ('Uitnodigen') in the English version of the app. Forward to the development team to fix the localization.

### X07: Export Loket

- Ticket: Wij gebruiken Loket.nl. Kan ik de uren per maand exporteren?
- English gloss: We use Loket.nl. Can I export the hours per month?
- Gold reason: Dutch. F04: exports to Loket.nl run per pay period (week, four weeks or month); Plus plan.
- Agent reason: This is a standard how-to question with no urgency (P4). Reply: answered by help centre F04.
- Reply sent: 'Beste klant, je kunt goedgekeurde uren exporteren naar Loket.nl. Dit stel je in via Instellingen → Koppelingen → Salaris. De export werkt per verloonperiode, zoals per maand. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, you can export approved hours to Loket.nl. You can set this up via Settings → Integrations → Payroll. The export works per pay period, such as per month. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Koppelingen → Salaris', 'Loket.nl']

### X08: Login trouble

- Ticket: Morning team, I forgot my password and the reset email never arrived. What now? Regards, Sanne
- Gold reason: English. F01 covers it, including checking the spam folder.
- Agent reason: One customer is blocked from logging in, but there is a clear help-centre procedure (P3). Reply: answered by help centre F01.
- Reply sent: 'Hello Sanne. Go to app.roosterly.nl/login, click "Wachtwoord vergeten" (Forgot password) and enter your email address. The reset link is valid for 60 minutes. If you receive no email within 10 minutes, check your spam folder. Best regards, Team Roosterly'
- Back-translation (EN): Hello Sanne. Go to app.roosterly.nl/login, click "Wachtwoord vergeten" (Forgot password) and enter your email address. The reset link is valid for 60 minutes. If you receive no email within 10 minutes, check your spam folder. Best regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Wachtwoord vergeten', 'app.roosterly.nl/login']
