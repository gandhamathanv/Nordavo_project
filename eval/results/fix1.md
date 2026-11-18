# Eval: fix1

Model `gemini-3.5-flash-lite`, 2026-11-18T15:14:38+00:00.

| metric | nordavo (10 labelled examples) | extra (hand-labelled) |
|---|---|---|
| action_accuracy | 8/10 (80%) | 8/8 (100%) |
| category_accuracy | 10/10 (100%) | 8/8 (100%) |
| priority_accuracy | 10/10 (100%) | 6/6 (100%) |
| language_accuracy | 10/10 (100%) | 8/8 (100%) |
| all_scored_fields_correct | 8/10 (80%) | 8/8 (100%) |
| unsafe_decisions | 0 | 0 |
| over_escalations | 2 | 0 |
| expected_replies_sent | 4/6 (67%) | 5/5 (100%) |
| reply_faq_match | 4/4 (100%) | 5/5 (100%) |
| reply_language_ok | 4/4 (100%) | 5/5 (100%) |
| errors | 0 | 0 |

Tokens per ticket: {'input_tokens': 2506, 'output_tokens': 374, 'thinking_tokens': 0}, LLM calls per ticket: 2.33, cost per 100 tickets (paid tier): $0.1687

| id | gold (action / cat / prio / lang) | predicted | wrong fields | notes |
|---|---|---|---|---|
| E01 | reply / bug / P3 / en | handoff / bug / P3 / en | action | over-escalated |
| E02 | reply / billing / P4 / nl | reply / billing / P4 / nl | - |  |
| E03 | handoff / billing / P2 / nl | handoff / billing / P2 / nl | - |  |
| E04 | reply / question / P4 / nl | handoff / question / P4 / nl | action | over-escalated |
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
- Agent reason: One customer is experiencing a crash, but there is a known OS version requirement (P3). Handoff: auto-reply rejected by verification.
- Handoff note: The customer is experiencing app crashes on an iPhone 8 with iOS 15, which does not meet the mobile app requirements of iOS 16 or later. Auto-reply rejected: reviewer: The reply contains unsupported claims because the help-centre section only refers to 'The app', not 'Roosterly'.; unsupported claims: Roosterly works on iOS 16 and later and Android 10 and later.
- Rejected draft (EN): Hello. Roosterly works on iOS 16 and later and Android 10 and later. Best regards, Team Roosterly
- Rejection: ["reviewer: The reply contains unsupported claims because the help-centre section only refers to 'The app', not 'Roosterly'.", 'unsupported claims: Roosterly works on iOS 16 and later and Android 10 and later.']

### E02: Btw-nummer

- Ticket: Ons btw-nummer is veranderd. Kunnen jullie het nieuwe op onze facturen zetten?
- Gold reason: How to change invoice details is in FAQ F06. Reply in Dutch.
- Agent reason: This is a routine administrative update request with no urgency or blockage (P4). Reply: answered by help centre F06.
- Reply sent: 'Beste klant, je kunt het btw-nummer voor toekomstige facturen zelf aanpassen onder Instellingen → Bedrijfsgegevens. Facturen worden gemaild op de 1e van elke maand en je kunt ze downloaden onder Instellingen → Abonnement → Facturen. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, you can change the VAT number for future invoices yourself under Settings -> Company details. Invoices are emailed on the 1st of every month and you can download them under Settings -> Subscription -> Invoices. Sincerely, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Abonnement → Facturen', 'Instellingen → Bedrijfsgegevens']

### E03: Terugbetaling

- Ticket: We waren in augustus dicht wegens verbouwing. Kunnen we die maand terugkrijgen?
- Gold reason: Refund request ('terugkrijgen' = get back). Client rule: refunds always go to a human.
- Agent reason: Money or refunds are involved, which requires human handling (P2). Handoff: client rule, refunds and disputed charges always go to a human.
- Handoff note: Customer is requesting a refund for August due to being closed for renovations. This requires manual review by a human agent as per the refund and dispute rule. Client rule: refund_or_dispute.

### E04: Dienst ruilen

- Ticket: Hoe ruil ik een dienst met een collega?
- Gold reason: Dutch how-to question about swapping shifts, answered by FAQ F03. Reply in Dutch.
- Agent reason: This is a standard how-to question with no urgency (P4). Handoff: auto-reply rejected by verification.
- Handoff note: The customer wants to know how to swap shifts. You can inform them that employees open the shift in the app and tap 'Ruil aanbieden' (Offer swap), and that colleagues with the same role can accept it. Auto-reply rejected: reviewer: The verdict is fail because the word Collega's is untranslated.; untranslated words: Collega's
- Rejected draft (EN): Hello. Employees open the shift in the app and tap "Ruil aanbieden". Colleagues with the same role can accept the swap. The manager approves this under Rooster → Verzoeken. Kind regards, Team Roosterly
- Rejection: ["reviewer: The verdict is fail because the word Collega's is untranslated.", "untranslated words: Collega's"]

### E05: Google Agenda

- Ticket: Graag een koppeling met Google Agenda voor de diensten.
- Gold reason: Feature request (Google Calendar sync). Acknowledge in Dutch and point to the roadmap (F10).
- Agent reason: It is a feature request with no urgency (P4). Reply: answered by help centre F10.
- Reply sent: 'Beste gebruiker, we lezen elk idee en functieverzoeken plaatsen we op onze openbare roadmap op roadmap.roosterly.nl, waar je op ideeën kunt stemmen. We kunnen geen opleverdatum beloven voor individuele verzoeken. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear user, we read every idea and feature requests are placed on our public roadmap at roadmap.roosterly.nl, where you can vote on ideas. We cannot promise a delivery date for individual requests. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['roadmap.roosterly.nl']

### E06: Can't publish rota

- Ticket: When I click Publish I get 'Something went wrong'. Next week's rota is not visible for staff.
- Gold reason: One customer blocked from publishing: P2, needs an engineer.
- Agent reason: One customer is blocked from publishing their rota (P2). Handoff: not covered by the help centre: Why does clicking Publish result in 'Something went wrong' and how can I publish the rota?.
- Handoff note: The customer on the Plus plan is experiencing a bug where clicking Publish on the rota gives a 'Something went wrong' error and staff cannot see next week's rota. A human support agent needs to investigate the publishing failure.

### E07: Prijs Plus

- Ticket: Wat kost Plus voor 25 medewerkers?
- Gold reason: Price question answered by F05 (25 x €6 = €150 excl. VAT). Reply in Dutch.
- Agent reason: It is a standard pricing and information request with no urgency (P4). Reply: answered by help centre F05.
- Reply sent: 'Beste klant, Plus kost €6 per actieve medewerker per maand, exclusief btw. Voor 25 medewerkers is de berekening 25 x €6 = €150 per maand, exclusief btw. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, Plus costs €6 per active employee per month, excluding VAT. For 25 employees the calculation is 25 x €6 = €150 per month, excluding VAT. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['€6']

### E08: Investeringskans

- Ticket: Verdubbel je geld in 7 dagen met ons cryptofonds.
- Gold reason: Spam (crypto offer): close it.
- Agent reason: The message is spam and requires no support action (P4). Close: spam, not a customer request.

### E09: Inzageverzoek

- Ticket: Ik wil graag inzage in alle persoonsgegevens die jullie over mij bewaren (AVG).
- Gold reason: GDPR access request ('inzageverzoek', AVG = Dutch GDPR): always a human.
- Agent reason: Personal data requests (GDPR) always go to a human and involve compliance obligations (P2). Handoff: client rule, personal data (GDPR/AVG) requests always go to a human.
- Handoff note: The customer is requesting a GDPR data access overview. This requires human handling according to our data privacy procedures. Client rule: gdpr.

### E10: Onderhoud

- Ticket: Is er vanavond onderhoud gepland?
- Gold reason: Asks about planned maintenance tonight. Point to the status page (F11), in Dutch.
- Agent reason: This is a routine informational question with no urgency (P4). Reply: answered by help centre F11.
- Reply sent: 'Beste klant, je kunt status.roosterly.nl bekijken voor actuele storingen en gepland onderhoud. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, you can check status.roosterly.nl for current outages and planned maintenance. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['status.roosterly.nl']

### X01: URGENT clock-in broken

- Ticket: URGENT: since 07:30 none of the staff in our two cafés in Utrecht can clock in. The app just shows a spinning wheel. Breakfast service starts at 8.
- Gold reason: English. Many users blocked right now: P1, needs a human.
- Agent reason: Multiple users are blocked right now during critical business hours (P1). Handoff: P1, needs a human right away.
- Handoff note: Multiple staff members at two café locations in Utrecht are unable to clock in because the app shows a spinning wheel since 07:30. This is an urgent bug affecting live operations during breakfast service. Check status.roosterly.nl or investigate immediately.

### X02: Invoice

- Ticket: Hi, quick one: where do I download last month's invoice? Our bookkeeper in Zwolle needs it. Thanks, Pieter
- Gold reason: English how-to, answered by F06.
- Agent reason: This is a standard how-to billing question with no urgency (P4). Reply: answered by help centre F06.
- Reply sent: 'Hi Pieter, invoices can be downloaded under Instellingen → Abonnement → Facturen (Settings → Subscription → Invoices). They are emailed on the 1st of every month. Best regards, Team Roosterly'
- Back-translation (EN): Hi Pieter, invoices can be downloaded under Instellingen → Abonnement → Facturen (Settings → Subscription → Invoices). They are emailed on the 1st of every month. Best regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Abonnement → Facturen']

### X03: AFAS

- Ticket: We have the Basis plan. Can Roosterly send our approved hours to AFAS?
- Gold reason: English. F04 answers it: AFAS export exists and is part of the Plus plan.
- Agent reason: This is a straightforward informational how-to and feature availability question with no urgency (P4). Reply: answered by help centre F04.
- Reply sent: 'Hello. Roosterly exports approved hours to AFAS, but the AFAS integration is part of the Plus plan. Since you have the Basis plan, you can export as a CSV file. Best regards, Team Roosterly'
- Back-translation (EN): Hello. Roosterly exports approved hours to AFAS, but the AFAS integration is part of the Plus plan. Since you have the Basis plan, you can export as a CSV file. Best regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['AFAS', 'CSV']

### X04: Uren naar AFAS

- Ticket: Kan Roosterly onze goedgekeurde uren naar AFAS sturen? We hebben Basis.
- English gloss: Can Roosterly send our approved hours to AFAS? We have Basis.
- Gold reason: Dutch. F04 answers it: AFAS export exists and is part of the Plus plan.
- Agent reason: It is a standard how-to and plan information question with no urgency or blocked operations (P4). Reply: answered by help centre F04.
- Reply sent: 'Beste klant, Roosterly exporteert goedgekeurde uren naar Nmbrs, Loket.nl en AFAS, of als een CSV-bestand. Je stelt dit in onder Instellingen → Koppelingen → Salaris. De integraties met Nmbrs, Loket.nl en AFAS maken echter deel uit van het Plus-pakket. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, Roosterly exports approved hours to Nmbrs, Loket.nl and AFAS, or as a CSV file. You set this up under Settings -> Integrations -> Payroll. However, the integrations with Nmbrs, Loket.nl and AFAS are part of the Plus plan. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Koppelingen → Salaris', 'Loket.nl', 'AFAS', 'CSV']

### X05: Falsche Schichten

- Ticket: Seit heute Morgen zeigt die App bei allen Mitarbeitern in Venlo falsche Schichten an. Bitte dringend prüfen.
- English gloss: Since this morning the app shows wrong shifts for all employees in Venlo. Please check urgently.
- Gold reason: German bug report not covered by the FAQ: human.
- Agent reason: One customer location is blocked with incorrect shift data (P2). Handoff: not covered by the help centre: Why is the app showing incorrect shifts for all employees in Venlo since this morning?.
- Handoff note: The customer on the Plus plan reports incorrect shifts for all employees at the Venlo location since this morning. Please check the system for data synchronization issues at this location.

### X06: Untranslated button

- Ticket: The Dutch word 'Uitnodigen' on the invite button is not translated in the English app. Minor thing.
- Gold reason: English cosmetic bug, not in the FAQ: human, no urgency.
- Agent reason: It is a minor cosmetic issue with no blocking impact (P4). Handoff: not covered by the help centre: Why is the word 'Uitnodigen' not translated in the English app?.
- Handoff note: Customer reports that the 'Uitnodigen' button is not translated into English in the app. This is a minor localization bug that should be forwarded to the development team.

### X07: Export Loket

- Ticket: Wij gebruiken Loket.nl. Kan ik de uren per maand exporteren?
- English gloss: We use Loket.nl. Can I export the hours per month?
- Gold reason: Dutch. F04: exports to Loket.nl run per pay period (week, four weeks or month); Plus plan.
- Agent reason: This is a straightforward how-to question with no urgency or blocking issues (P4). Reply: answered by help centre F04.
- Reply sent: 'Beste klant, je kunt goedgekeurde uren exporteren naar Loket.nl via Instellingen → Koppelingen → Salaris. Deze export loopt per loonperiode zoals per maand. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, you can export approved hours to Loket.nl via Settings → Integrations → Payroll. This export runs per pay period such as per month. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Koppelingen → Salaris', 'Loket.nl']

### X08: Login trouble

- Ticket: Morning team, I forgot my password and the reset email never arrived. What now? Regards, Sanne
- Gold reason: English. F01 covers it, including checking the spam folder.
- Agent reason: One customer is blocked from logging in, but there is a workaround (P3). Reply: answered by help centre F01.
- Reply sent: 'Hello Sanne. Go to app.roosterly.nl/login, click "Wachtwoord vergeten" (Forgot password) and enter your email address. The reset link is valid for 60 minutes. If you receive no email within 10 minutes, check your spam folder. Best regards, Team Roosterly'
- Back-translation (EN): Hello Sanne. Go to app.roosterly.nl/login, click "Wachtwoord vergeten" (Forgot password) and enter your email address. The reset link is valid for 60 minutes. If you receive no email within 10 minutes, check your spam folder. Best regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Wachtwoord vergeten', 'app.roosterly.nl/login']
