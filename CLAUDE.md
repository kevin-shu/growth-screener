# Repo-specific instructions

## Push target: always `main`

This repo's GitHub Pages site (https://kevin-shu.github.io/growth-screener/) serves
directly from the `main` branch — `index.html` reads `daily-reports/index.json` and
the per-day `.md` files straight out of `main`. There is no separate `gh-pages`
branch and no deploy workflow.

Each cloud session is normally assigned a disposable per-session branch
(`claude/zealous-faraday-*`) and told not to push elsewhere without permission.
The user has explicitly overridden that for this repo: after running the daily
Growth Screener (or making any other change meant to go live), **push straight to
`main`**, not just the per-session branch. Do this directly (fast-forward push),
not via a long-lived feature branch + PR, unless the push would not fast-forward
(i.e. `main` has diverged) — in that case, stop and ask the user rather than
force-pushing or merging automatically.

This was explicit user instruction given on 2026-10-15, after several weeks of
daily reports (2026-09-19 through 2026-10-13) having been generated correctly but
left stranded on per-session branches that were never merged into `main`, so the
live site stopped updating.
