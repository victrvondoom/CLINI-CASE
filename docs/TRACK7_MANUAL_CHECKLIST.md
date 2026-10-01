# Manual items remaining

These items require credentials, rights evidence or external decisions. Technical work continued without waiting for them.

1. **Live AI:** replace the rejected `OPENROUTER_API_KEY` locally in `.env`, never in chat or Git. Run `./start-track7.ps1 -AI` and confirm real typed suggestions. The deterministic reference journey is verified; live AI acceptance is not yet verified.
2. **GitHub publishing:** authenticate Git for `victrvondoom/CLINI-CASE`. Push the committed hardening branch only to `https://github.com/victrvondoom/CLINI-CASE.git`. No changes were pushed to `vsrupeshkumar/CLINICASE`.
3. **Judge access:** you confirmed authorization exists. Retain the signed authorization and ensure it explicitly permits judges to run/review the code. The proprietary LICENSE is preserved; the underlying document was not independently inspected. See [judge access](JUDGE_ACCESS.md).
4. **Eligibility:** obtain organizer clarification on reused platform code and Oct 1 hardening. The [rules](https://oneaquahealth-ieee-hackathon.devpost.com/rules) specify Sept 16–30 development; the [deadline update](https://oneaquahealth-ieee-hackathon.devpost.com/updates) extends submission to Oct 4, 9pm PDT. A submission extension does not prove a development extension. Use the accurate [build scope](HACKATHON_BUILD_SCOPE.md), and disclose Claude/Codex assistance.
5. **Full conformance:** load the pinned OAH implementation guide and a terminology service into the official validator; resolve/report warnings. Verify any future standard terminology mappings against an authoritative server. Current local codes are not represented as verified LOINC or SNOMED.
6. **Pilot:** seek a district health office/laboratory partner for a consented workflow/usability pilot. Current data and measurements are synthetic; no real users, clinical accuracy or health improvement is claimed.
7. **Deployment secrets:** review existing ignored `.env` and legacy development accounts before exposure. New demo launchers use private generated passwords, but existing database passwords/accounts were deliberately not overwritten. Use production secrets and receiver authentication outside localhost.

These are readiness gaps, not fabricated completed outcomes or a promised judge score.
