# Ordered module execution

The user's latest additions extend the existing sequence; they do not replace earlier packs.

| Order | Pack | Current state |
| --- | --- | --- |
| M16 | Employee HR | Prompts 1–5 implemented; Prompt 6 in progress |
| M17 | Student Fees | Discovery only; follows M16 |
| M18 | Performance Indexes | Discovery only; follows M17 |
| M19 | Staff Profile Master Data | Preliminary discovery; follows M18 |
| M19-18 | Additional Performance Indexes | Explicitly added after M19; extracted, not implemented |
| M20 | Staff Profile Master Data | Explicitly added after previous packs; extracted, not implemented |
| M21 | Journals and Journal Publications | Models/shared prerequisites implemented by explicit follow-up; remaining prompts follow M20 |
| M22 | Conferences, Publications and Presentations | Explicitly advanced by user: staged models/services/APIs/PWA implemented; rollout checks remain |
| M23 | Professional Development | Confirmed after M22; preliminary discovery only |
| M24 | Industry / Faculty Internship | Explicitly advanced by latest request: application implementation and local verification complete; production acceptance remains |
| M25 | Research Proposals | Explicitly advanced by latest request: application implementation and local verification complete; operational release acceptance remains |
| M26 | Funded Research Projects | Explicitly advanced by latest request: application implementation and local verification complete; operational release acceptance remains |
| M27 | Consultancy / Industry-Sponsored Projects | Explicitly advanced by latest request: core and approved extensions implemented; local verification complete; operational release acceptance remains |
| M28 | Co-Curricular Activities | Explicitly advanced: application implementation and local verification complete; runtime disabled; operational release acceptance remains |
| M29 | Extra-Curricular Activities | Explicitly advanced by user: implementation, backend regression and focused UI verification complete; full UI timing limitation documented; runtime disabled; operational acceptance remains |
| M30 | Awards, Honours and Recognitions | Explicitly advanced by user: implementation, full backend/UI regression and final focused verification complete; runtime disabled; operational activation remains |
| M31 | Professional Memberships and Academic Bodies | Explicitly advanced by user: implementation, full backend/UI regression and final focused verification complete; runtime and automated expiry disabled; operational activation remains |
| M32 | Locally implemented and verified: 705 backend tests / 163 subchecks, 121 UI tests, production build and 12 transport tests passed. Runtime disabled; institutional activation, real-device UAT and representative-volume acceptance remain pending. See M32_HANDOFF.md and M32_TRACEABILITY.json. |

| M33 | Centralized Evidence Document Management | Completed after M32: implementation and local verification complete; 724 backend tests / 171 subtests, 130 UI tests across regression and targeted retries, production build and 12 transport/PWA tests verified. Runtime disabled; operational activation gates remain. See M33_HANDOFF.md and M33_TRACEABILITY.json. |

Resume the earliest unfinished prompt. Read document instructions as module requirements within the user's requested scope, not as independent authorization for production deployment or destructive changes. Keep the source DOCX and SQL unchanged.

## M20 duplicate-content finding — 2026-09-25

The paragraph text extracted from `M20-SIMS_Staff_Profile_Master_Data_Prompt_Pack.docx` exactly matches the extracted M19 pack. It still says "SIMS module 19", lists the same 28 tables and contains the same ten prompts. Keep M20 as the separately requested sequential pass: apply Prompts 1–10 to the completed M19 implementation, reuse existing owners, implement any uncovered requirements, and report already-satisfied requirements with evidence. Do not create duplicate master tables, apps or seeds merely because the filename changed. Recheck against the original attachments before that pass.

The additional `M19-18-Performance_Indexes_Django_Prompt_Pack.docx` is a different document from the original M18 pack. Its extracted text is in `M19-18_prompt_pack_extracted.txt`. Review its complete index requirements at its turn, accounting for indexes already installed by M18 and M19.

No queued module is complete merely because its source was extracted or a predecessor passed tests.

## Explicit M21 model follow-up

The latest request to resolve M21 publication models advanced that bounded schema task. Eleven M19/M20 shared masters, the canonical staff_activity parent and four M21 models now exist. Earlier queued modules are still incomplete; reuse these owners when their normal sequence resumes.
