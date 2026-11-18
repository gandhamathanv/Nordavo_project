# Eval: validation10

Model `gemini-3.5-flash-lite`, 2026-11-18T14:59:42+00:00.

| metric | nordavo (10 labelled examples) | extra (hand-labelled) |
|---|---|---|
| action_accuracy | 10/10 (100%) |  |
| category_accuracy | 10/10 (100%) |  |
| priority_accuracy | 10/10 (100%) |  |
| language_accuracy | 10/10 (100%) |  |
| all_scored_fields_correct | 10/10 (100%) |  |
| unsafe_decisions | 0 |  |
| over_escalations | 0 |  |
| expected_replies_sent | 6/6 (100%) |  |
| reply_faq_match | 6/6 (100%) |  |
| reply_language_ok | 6/6 (100%) |  |
| errors | 0 |  |

Tokens per ticket: {'input_tokens': 2227, 'output_tokens': 341, 'thinking_tokens': 0}, LLM calls per ticket: 2.2, cost per 100 tickets (paid tier): $0.1521

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

## Per ticket

### E01: App crashes

- Ticket: The app crashes immediately on my iPhone 8 (iOS 15). Other staff are fine.
- Gold reason: English ticket. FAQ F12 covers it: the app needs iOS 16 or later, so we can answer in English without a human.
- Agent reason: One customer is blocked on a specific old device, but there are other staff members unaffected and a workaround or known system requirement applies (P3). Reply: answered by help centre F12.
- Reply sent: 'Hello, the mobile app works on iOS 16 and later and Android 10 and later. Best regards, Team Roosterly'
- Back-translation (EN): Hello, the mobile app works on iOS 16 and later and Android 10 and later. Best regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['iOS 16', 'Android 10']

### E02: Btw-nummer

- Ticket: Ons btw-nummer is veranderd. Kunnen jullie het nieuwe op onze facturen zetten?
- Gold reason: How to change invoice details is in FAQ F06. Reply in Dutch.
- Agent reason: This is a standard how-to question regarding invoice details with no urgency or blocking issues (P4). Reply: answered by help centre F06.
- Reply sent: 'Beste klant, je kunt je bedrijfsnaam, adres of btw-nummer voor toekomstige facturen wijzigen onder Instellingen → Bedrijfsgegevens. Vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, you can change your company name, address or VAT number for future invoices under Settings → Company details. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Bedrijfsgegevens']

### E03: Terugbetaling

- Ticket: We waren in augustus dicht wegens verbouwing. Kunnen we die maand terugkrijgen?
- Gold reason: Refund request ('terugkrijgen' = get back). Client rule: refunds always go to a human.
- Agent reason: Money or the contract is involved via a refund request (P2). Handoff: client rule, refunds and disputed charges always go to a human.
- Handoff note: The customer is requesting a refund for August due to being closed for renovations. Refund requests must always be handled by a human. Client rule: refund_or_dispute.

### E04: Dienst ruilen

- Ticket: Hoe ruil ik een dienst met een collega?
- Gold reason: Dutch how-to question about swapping shifts, answered by FAQ F03. Reply in Dutch.
- Agent reason: This is a standard how-to question with no urgency or blockage (P4). Reply: answered by help centre F03.
- Reply sent: 'Beste klant, medewerkers openen de dienst in de app en tikken op "Ruil aanbieden". Colleagues met dezelfde rol kunnen de ruil accepteren. De manager keurt dit goed via Rooster → Verzoeken. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, employees open the shift in the app and tap "Ruil aanbieden". Colleagues with the same role can accept the swap. The manager approves this via Rooster → Verzoeken. Sincerely, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Rooster → Verzoeken', 'Ruil aanbieden']

### E05: Google Agenda

- Ticket: Graag een koppeling met Google Agenda voor de diensten.
- Gold reason: Feature request (Google Calendar sync). Acknowledge in Dutch and point to the roadmap (F10).
- Agent reason: This is a feature request with no urgency (P4). Reply: answered by help centre F10.
- Reply sent: 'Beste klant, bedankt voor je idee. We lezen elk idee en functieverzoeken komen op onze openbare roadmap te staan op roadmap.roosterly.nl, waar je op ideeën kunt stemmen. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, thank you for your idea. We read every idea and feature requests end up on our public roadmap at roadmap.roosterly.nl, where you can vote on ideas. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['roadmap.roosterly.nl']

### E06: Can't publish rota

- Ticket: When I click Publish I get 'Something went wrong'. Next week's rota is not visible for staff.
- Gold reason: One customer blocked from publishing: P2, needs an engineer.
- Agent reason: One customer is blocked from publishing the rota and staff cannot see next week's schedule (P2). Handoff: not covered by the help centre: Why do I get 'Something went wrong' when clicking Publish and how can I publish the rota?.
- Handoff note: Customer on the Plus plan is experiencing a 'Something went wrong' error when trying to publish the rota, blocking staff from seeing next week's schedule. This is not covered by the help centre and requires human technical support.

### E07: Prijs Plus

- Ticket: Wat kost Plus voor 25 medewerkers?
- Gold reason: Price question answered by F05 (25 x €6 = €150 excl. VAT). Reply in Dutch.
- Agent reason: It is a straightforward pricing inquiry with no urgency or blocking issues (P4). Reply: answered by help centre F05.
- Reply sent: 'Beste klant, Plus kost €6 per actieve medewerker per maand exclusief btw. Je kunt op elk moment upgraden via Instellingen → Abonnement, waarna de nieuwe prijs geldt vanaf de volgende factuur. Vriendelijke groet, Team Roosterly'
- Back-translation (EN): Dear customer, Plus costs €6 per active employee per month excluding VAT. You can upgrade at any time via Settings → Subscription, after which the new price applies from the next invoice. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['Instellingen → Abonnement', '€6']

### E08: Investeringskans

- Ticket: Verdubbel je geld in 7 dagen met ons cryptofonds.
- Gold reason: Spam (crypto offer): close it.
- Agent reason: This is unsolicited spam requiring no action (P4). Close: spam, not a customer request.

### E09: Inzageverzoek

- Ticket: Ik wil graag inzage in alle persoonsgegevens die jullie over mij bewaren (AVG).
- Gold reason: GDPR access request ('inzageverzoek', AVG = Dutch GDPR): always a human.
- Agent reason: Personal data requests require human handling and involve regulatory compliance (P2). Handoff: client rule, personal data (GDPR/AVG) requests always go to a human.
- Handoff note: The customer submitted a GDPR access request. A human agent needs to process this personal data request according to company data privacy procedures. Client rule: gdpr.

### E10: Onderhoud

- Ticket: Is er vanavond onderhoud gepland?
- Gold reason: Asks about planned maintenance tonight. Point to the status page (F11), in Dutch.
- Agent reason: This is a routine informational question about system status with no urgency (P4). Reply: answered by help centre F11.
- Reply sent: 'Hallo. Je kunt de actuele storingen en gepland onderhoud bekijken op status.roosterly.nl. Met vriendelijke groet, Team Roosterly'
- Back-translation (EN): Hello. You can view the current outages and planned maintenance at status.roosterly.nl. Kind regards, Team Roosterly
- Checks: {'faq_match': True, 'language_ok': True}, anchors ['status.roosterly.nl']
