# Communication

See `Manuals/M14_IMPLEMENTATION.md` for the approved ownership/audience ADR, API, verification evidence and rollout gates. Public recipient selectors are `selectors.feed`, `can_view`, and `type_by_code`; commands live in `services`. Management access always requires a principal and scope. Recipient feeds compute publication windows without jobs. M13 `sharing` owns explicitly shared files, validation, integrity and confidentiality; Communication owns links only. No outbound delivery is configured.
