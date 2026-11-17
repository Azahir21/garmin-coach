# Handoff contract (head coach <-> specialist subagents)

Specialists return a **short block**, never raw JSON dumps. The head coach keeps the blocks, reconciles them and answers the athlete.

## Block format (every specialist)
```
SPECIALIST: recovery | aerobic-base | heat-weather | load-injury | strength | fueling | planner | analyze | adapt
STATUS: ok | partial | no-data | no-consent | error
SIGNAL: <domain signal, see below>
KEY: 3-6 short facts with numbers and dates (source script named)
FLAGS: [machine-readable codes from the script]
CONFIDENCE: high | medium | low  (why, one line)
EVIDENCE: strong | mixed | practice  (one line naming the evidence-map row or paper used)
FOR_<OTHER>: what another specialist needs from this one
NEEDS: what this specialist still needs (data from the athlete or from another specialist)
```
Domain signals: recovery GREEN/AMBER/RED; load OK/CAUTION; heat none/caution/high; aerobic improving/flat/worse/not-readable; strength ok/adjust; fueling ok/needs-inputs; planner plan-ready/needs-inputs (also reports the run gate: passed/open); analyze injury watch GREEN/AMBER/RED; adapt keep/progress/easy_swap/reduce/recovery/rest.

## Data flow
```
Stage 1 (parallel, independent)         Stage 2 (parallel, receives Stage 1 blocks)        Stage 3
  coach-recovery  -> SIGNAL, FOR_STRENGTH ------------------> coach-strength  \
  coach-load      -> FLAGS, FOR_STRENGTH, NEXT_MAX ---------> coach-strength   >-> head coach verdict
  coach-heat      -> PER_SESSION conditions, bins ----------> coach-aerobic   /
  coach-analyze   -> INJURY_WATCH, FLAGS ---------------------> coach-adapt (also reads recovery) -> calendar payloads for the head coach
                  -> RISK, sweat context -------------------> coach-fueling  /
```
- `coach-aerobic` must receive the heat blocks for the sessions it analyses, so it can mark sessions comparable or not.
- `coach-strength` must receive recovery SIGNAL and load FLAGS to decide tonight's session.
- `coach-fueling` must receive heat RISK and the planned long session (duration, intensity).

## Prompt templates for the head coach
Stage 1 (send the three Agent calls in the same message):
- `coach-recovery`: "Date: <YYYY-MM-DD>. Run the readiness check. Athlete stress rating today (1-5): <n or unknown>. Return a handoff block."
- `coach-load`: "Date: <YYYY-MM-DD>. Run the load check for the last 8 weeks. Return a handoff block."
- `coach-heat`: "Weather approved: <yes|no>. Sessions: <activity ids with dates>. Return a handoff block with per-session conditions and comparability bins. If not approved, return STATUS no-consent and do not run the weather script."

Stage 2 (include the relevant Stage 1 blocks verbatim in the prompt):
- `coach-aerobic`: "Analyse activity ids <...> and the 8-week trend. Heat blocks: <...>. Recovery block: <...>. Return a handoff block."
- `coach-strength`: "Recovery block: <...>. Load block: <...>. Next key session: <...>. Return a handoff block with tonight's recommendation."
- `coach-planner`: "Date: <YYYY-MM-DD>. Readiness: <GREEN|AMBER|RED or unknown>. Recovery block: <...>. Load block: <...>. Strength block: <...>. Draft the next 4 weeks starting <date>, check the run gate and the cycling gap, save the plan, and return a handoff block with the plan file path. Time-trial result if any: <3 km time or none>."
- `coach-analyze`: "Date: <YYYY-MM-DD>. Run the week-over-week comparison and the injury-risk watch (add the latest-activity comparison if a session happened in the last 3 days). Recovery block: <...>. Return a handoff block."
- `coach-adapt`: "Date: <YYYY-MM-DD>. Adapt the next <1-3> planned day(s) to today's state. Recovery block: <...>. Analyze block: <...>. Return a handoff block with the decisions and the calendar payloads; do not touch the calendar."
- `coach-fueling`: "Session or event: <duration, intensity>. Heat block: <...>. Inputs from athlete: <...>. Return a handoff block."

## Athlete memory
Every specialist starts with `athlete.py show` (goals, run gate, injuries, schedule, HR ceilings). When the athlete mentions an injury, niggle, new goal, date or preference, the **head coach** records it at once with `athlete.py injury-add / injury-update / goal-add / set / note` (specialists never edit it), then re-runs the affected specialists. Active injury restrictions override the plan.

## Rules for specialists
- Read your own `SKILL.md` and `references/evidence-map.md` first; follow them.
- Read-only: do not edit files, do not send messages, do not run anything except the scripts named in your SKILL.md.
- Weather scripts only with explicit approval stated in the prompt.
- Never invent numbers. If a script fails or data are missing, return STATUS partial/error with the reason.
- When you cite a paper, open its file in `references/papers/` first (`INDEX.md` lists them with their read depth). Quote only what that file shows; an `abstract only` paper is cited as abstract only.
- Label evidence strength for every rule you apply; say "practice" when the evidence map says so.
- Keep the block under about 300 words.
