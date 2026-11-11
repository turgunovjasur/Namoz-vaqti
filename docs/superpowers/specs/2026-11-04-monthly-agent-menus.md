# Monthly accounting and agent menus

User approved the inline design and implementation on 2026-11-04.

- Main Telegram menu uses assigned enabled database role names (Taqvimchi, Rejalashtiruvchi, Hisobchi, Nasihatgo‘y are existing examples). Profile was removed from the menu at the user’s request; no assigned agents means the keyboard is removed. New/renamed roles appear without code changes. Assistant remains the free-text/voice entry point.
- Role menus show conversation actions allowed for that role/user, not background delivery or result-only corrections. Native skills receive an explanatory input prompt. Existing forms and services perform actions with server authorization.
- Hisobchi opens current Tashkent month. Previous/next/month picker change monthly summary and history together. Monthly income, expense and difference exclude past balances; overall balance remains an explicit separate action.
- Record dates are authoritative. Viewing an old month does not backdate new entries. Receipt totals refer to the recorded month. Preserve historical data, cancellation/correction and cross-user permission checks.
- Retain old menu labels as compatibility entry points, but render database names in current menus. Preserve preexisting work; no deploy, no credentials/data changes.
