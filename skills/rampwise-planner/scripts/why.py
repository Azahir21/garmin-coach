"""Plain-language 'why this session matters' and 'check after' texts for the plan and the calendar.

Every text ends with an evidence label that matches ../references/evidence-map.md: what a paper found (research),
what is a coaching convention (practice). Keep sentences short and free of jargon: the athlete asked for notes that
explain why each session is in the plan.
"""

WHY = {
    "run_easy": (
        "Easy running at a heart rate of {ceil} or less builds your aerobic base: the engine behind your running and riding goals. "
        "Keeping it easy lets you repeat it 5-6 days a week without getting hurt.",
        "Evidence: research for easy-focused training in recreational runners (Zinner 2018, Festa 2019); the ceiling and the warm-up / zone 2 / cool-down layout are practice."),
    "run_long": (
        "The longest run of the week builds endurance (time on your feet) and is your best test of how your base is growing. "
        "It grows by at most 10% over your longest run so far, because one run much longer than your recent longest was linked with more injuries.",
        "Evidence: observational (Frandsen 2025) for the 10% cap; the layout is practice."),
    "run_short": (
        "A short easy run after the long ride keeps running frequent and loosens your legs with very little extra load. Frequent easy running is how the aerobic base grows without big jumps.",
        "Evidence: practice."),
    "run_strides": (
        "Six short, relaxed fast strides teach smooth running form and a little speed with almost no extra tiredness. The rest is easy running, so the aerobic base keeps growing. "
        "Fast work stays at 20% of the week or less.",
        "Evidence: practice; the 20% share comes from trials of mostly-easy training (Neal 2013, Festa 2019)."),
    "run_tt": (
        "A 3 km effort at an even pace gives your first real pace numbers. The coach uses it to set your pace zones and to see how far your running goals are from where you are today.",
        "Evidence: practice; treat the result as a starting point."),
    "ride_easy": (
        "Easy rides add aerobic volume with little stress on your legs, so you can train most days. They build the aerobic base for your riding goals.",
        "Evidence: research for mostly-easy training (Seiler 2010 review); the heart-rate band is practice."),
    "ride_long": (
        "The long ride is the key session for long-ride goals: steady time in the saddle at an easy heart rate. Use the same bike and route when you can, so changes in speed are readable. "
        "On rides of 90 minutes or more, plan food and drink.",
        "Evidence: practice; for food and drink see Jeukendrup 2014."),
    "ride_intervals": (
        "Short hard efforts with full recovery raise your top end, which is what lifts your average speed. The rest of the ride is easy, so the hard time stays at 20% of the week or less.",
        "Evidence: practice; trained cyclists improved more with about 20% hard work (Neal 2013)."),
    "run_maf": (
        "Once a month you run the same 5 km at the same heart rate ({maf} bpm), so any change in pace is a clean reading of your aerobic fitness: if the pace at {maf} gets faster, the base is growing. "
        "It replaces that week's long run, so it adds no extra volume. Run the same course each time, at a similar time of day.",
        "Evidence: practice. Pace at a fixed heart rate is used to track fitness (Vesterinen 2016/2017); the {maf} comes from the MAF formula (180 - age - 5), which its authors say still has to be verified scientifically (Maffetone & Laursen 2020)."),
    "run_tempo": (
        "A steady block at a hard-but-controlled heart rate ({lo}-{hi}) teaches you to hold a faster pace for longer. It is the step between easy running and 10 km pace. "
        "Hard time stays at 20% of the week or less.",
        "Evidence: practice (a coaching convention); the 20% share comes from trials of mostly-easy training (Neal 2013, Festa 2019)."),
    "run_intervals": (
        "Short hard repeats with real rests raise your top speed and make a faster pace feel less hard. The rest steps let your heart rate drop, so the hard time stays at 20% of the week or less.",
        "Evidence: practice; trials of mostly-easy plans with a small hard share used about 20% (Neal 2013, Festa 2019, Stoggl 2014)."),
    "ride_climb": (
        "Climbing builds leg strength at low speed, which helps your average speed on flat routes, and trains your heart to recover between efforts. If hills are few where you ride, the plan counts total ascent: repeat a short climb until the watch shows it. "
        "It replaces the aerobic ride of that day, so it adds no extra volume.",
        "Evidence: practice; I read no study on climbing for recreational cyclists. Stay seated, keep it steady and use easy gears; ease off if something complains."),
    "strength_A": (
        "Strength work improves running and cycling economy: you use less energy at the same speed. Monday is the lower-body day: it follows Sunday's short run and comes before easy days. "
        "Single-leg moves and slow lowering make light plates hard, and they train the stabilising muscles around the hips and knees.",
        "Evidence: research for heavy or explosive strength (Ronnestad & Mujika 2014); with light plates the single-leg version is practice and may help less."),
    "strength_B": (
        "Upper body and core work keeps your posture strong on the bike and your running form steady late in a session. The legs stay light because a long run or ride follows, and tired legs there raise injury risk.",
        "Evidence: practice."),
}

CHECK = {
    "run_easy": "Was the average heart rate at or under {ceil}? What was the pace at that heart rate? Did the session feel easy?",
    "run_long": "Did you finish as planned? How did your legs and joints feel the next morning? Note how the last 10 minutes felt.",
    "run_short": "It should feel easy and short. If your legs are heavy, shorten it or swap it for rest.",
    "run_strides": "The strides should feel quick and relaxed, not hard. Your heart rate returns to easy within the 70 s rest.",
    "run_tt": "Send the time to the coach. It is your first pace anchor.",
    "ride_easy": "Note moving speed and average heart rate. The same effort should get a little faster over weeks.",
    "ride_long": "Note moving speed, average heart rate and total climb. Compare only with long rides on the same route.",
    "ride_intervals": "Heart rate should come down during each rest. If it does not, ride easy instead.",
    "run_maf": "Write down the pace of each of the 5 test kilometres (the watch laps them). The first and last km show how well you hold the pace at {maf}. Compare with last month on the dashboard (Running page).",
    "run_tempo": "Heart rate should settle in {lo}-{hi} within the first few minutes of the block. Note the pace you held.",
    "run_intervals": "Heart rate should come down during each rest. If it does not, stop after the next repeat.",
    "ride_climb": "Note the total ascent on the watch (goal: {target} m), the average heart rate on the climbs and how your legs felt the next morning.",
    "strength_A": "Last 2 reps hard, 2-3 left in reserve. Pain is a stop sign.",
    "strength_B": "Light and controlled. You should feel fresh the next morning.",
}


def _fill(text, fmt):
    """No heart-rate band known for the hard effort (the athlete shared no zones or tempo band): say 'by feel' instead of numbers."""
    if "lo" in fmt and (fmt["lo"] is None or fmt["hi"] is None):
        text = text.replace("({lo}-{hi})", "(by feel: you can say only a few words)").replace("settle in {lo}-{hi}", "settle at a hard but steady level")
    return text.format(**fmt)


def why_text(kind, **fmt):
    reason, evidence = WHY[kind]
    return _fill(reason + " " + evidence, fmt)


def check_text(kind, **fmt):
    return _fill(CHECK[kind], fmt)
