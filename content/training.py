"""
Training content for the Luckmaxxing Protocol.

Format: list of (speaker, message) tuples.
  speaker is either "Intern" (coach) or "Gamblors" (students / user response).

Day 1 -> First real lesson (sent immediately when the user activates the
         initiation button on enrollment — see views/dm_ritual.py)
Days 2-8 -> Delivered automatically every 24 hours.
"""

import os

from database.training_videos import get_training_video

# Per-day banner images live here as day1.jpg, day2.png, etc. — dropped in by
# hand as each one is provided, no DB row or redeploy of code logic needed.
_BANNER_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "day_banners")
_BANNER_EXTS = ("jpg", "jpeg", "png", "webp")

DAY_1 = [
    (
        "Intern",
        "Your first day in the training requires a new beginning. In order for your new self "
        "to be born, your old self must die. Forget what you think you know about luck. "
        "Forget your lucky or unlucky past. Cleanse yourself of your peak net worth.",
    ),
    ("Gamblors", "Forgetting, Chief."),
    (
        "Intern",
        "Luck is a skill. By 2026 there's enough scientific evidence to prove so, and by 2033 "
        "this will become unquestionable even for normies. Research Richard Wiseman, research "
        "Dean Radin. Both are ahead of their time and now you can be too for 7 years until "
        "normies catch up.",
    ),
    ("Gamblors", "I will research, Chief!"),
    (
        "Intern",
        "Luck is a skill. And as such, you will learn to cultivate it. "
        "Now repeat after me: Luck is a skill!",
    ),
    ("Gamblors", "Luck is a skill!"),
    (
        "Intern",
        "Good. Cultivation begins with conviction. Mantras will be our tool to boost such "
        "conviction. Today our exercise consists in ingraining one of the most powerful "
        "luckmaxxing mantras into your being. Take 30 seconds to breathe in and out. "
        "Begin to feel your luck.",
    ),
    ("Gamblors", "Breathing!"),
    ("Intern", "Do the actual breathing, don't skip any command!"),
    ("Gamblors", "(Breathing...)"),
    (
        "Intern",
        'Good, now you are ready. Repeat calmly after me. "I am lucky. I am the luck."',
    ),
    ("Gamblors", "I am lucky. I am the luck."),
    ("Intern", "Again, harder."),
    ("Gamblors", "I AM LUCKY. I AM THE LUCK."),
    ("Intern", "Louder. Convince the universe."),
    ("Gamblors", "I AM LUCKY. I AM THE LUCK!!!"),
    (
        "Intern",
        "Good. You will now repeat this mantra daily before sunrise and before you engage in "
        "any high-risk activity until it becomes a part of you. Pay close attention throughout "
        "the day - its effects won't go unnoticed.",
    ),
    ("Gamblors", "Yes sir!"),
    (
        "Intern",
        "Congratulations gamblors. Where 88 % of gamblors fail and think our exercises are "
        "retarded, you pushed through and made it. You can proceed to Day 2 tomorrow.",
    ),
    ("Gamblors", "Thank you Chief!"),
]

DAY_2 = [
    (
        "Intern",
        "Welcome to Day 2, gamblor. Yesterday you built conviction. Today you will build "
        "attention. Luck favors the person who notices the tiny opening before everyone else.",
    ),
    ("Gamblors", "I will notice, Chief!"),
    (
        "Intern",
        "For the next 24 hours you will stop moving through your day on autopilot. "
        "Every room, every chat, every timeline, every market tab: scan first, act second.",
    ),
    ("Gamblors", "Scan first. Act second."),
    (
        "Intern",
        "Your exercise is simple. Three times today, pause for ten seconds and ask: "
        '"What is the overlooked opening here?"',
    ),
    ("Gamblors", "I will look for the opening."),
    (
        "Intern",
        "Good. Luck is often dismissed as randomness because average people never train their "
        "pattern recognition. You are not average anymore.",
    ),
    ("Gamblors", "Not average, Chief."),
    (
        "Intern",
        "When you spot an opening, write it down somewhere. Do not judge it immediately. "
        "The first step is learning to see more than the herd sees.",
    ),
    ("Gamblors", "I will record what I notice."),
    (
        "Intern",
        "Before you leave, repeat the line for today: I notice the door before it opens for others.",
    ),
    ("Gamblors", "I notice the door before it opens for others."),
]

DAY_3 = [
    (
        "Intern",
        "Day 3 begins now. Today we clean your environment. Bad luck multiplies in clutter, "
        "hesitation, and unfinished signals.",
    ),
    ("Gamblors", "Then we purge it, Chief."),
    (
        "Intern",
        "Look at your room, your desktop, your tabs, your notifications. Every piece of noise "
        "steals attention from useful signals.",
    ),
    ("Gamblors", "Noise is the enemy."),
    (
        "Intern",
        "Your exercise: remove one obvious source of friction from your life today. "
        "A messy desk. A chaotic note app. A pointless tab farm. Anything that keeps you fuzzy.",
    ),
    ("Gamblors", "I will remove the friction."),
    (
        "Intern",
        "Luck is easier to receive when your mind is not fighting twenty small battles at once. "
        "Order is not aesthetic. Order is leverage.",
    ),
    ("Gamblors", "Order is leverage."),
    ("Intern", "Finish with today's line: I make space for good outcomes to land."),
    ("Gamblors", "I make space for good outcomes to land."),
]

DAY_4 = [
    (
        "Intern",
        "Welcome to Day 4. Today you begin collecting proof. The undisciplined mind forgets "
        "what worked and repeats what failed.",
    ),
    ("Gamblors", "I will collect the proof, Chief."),
    (
        "Intern",
        "Create a small luck journal. Nothing fancy. One note is enough. When something goes "
        "unexpectedly well, write what happened right before it.",
    ),
    ("Gamblors", "Cause before effect. Understood."),
    (
        "Intern",
        "Did you speak to someone new? Pause before acting? Enter with confidence? Follow a weird "
        "hunch? We are mapping the conditions that precede favorable outcomes.",
    ),
    ("Gamblors", "I will map the conditions."),
    (
        "Intern",
        "Do the same for obvious failures. Not to shame yourself. To remove the fog. "
        "You cannot refine what you refuse to observe.",
    ),
    ("Gamblors", "No fog, Chief."),
    ("Intern", "Today's line: I study my fortune like a scientist."),
    ("Gamblors", "I study my fortune like a scientist."),
]

DAY_5 = [
    (
        "Intern",
        "Day 5. You're past the midpoint, which means the real enemy appears now: emotional noise. "
        "Tilt, urgency, and desperation destroy clean judgment.",
    ),
    ("Gamblors", "No tilt. No desperation."),
    (
        "Intern",
        "When you feel urgency spike today, you will not act immediately. You will breathe once, "
        "sit back, and let the impulse lose five percent of its force before you decide.",
    ),
    ("Gamblors", "I choose after the spike, not inside it."),
    (
        "Intern",
        "This is how lucky people separate themselves. They do not hand the wheel to panic. "
        "They let others rush, then take the cleaner line.",
    ),
    ("Gamblors", "Cleaner line, Chief."),
    (
        "Intern",
        "Your exercise: catch yourself once today in a rushed state and deliberately slow down. "
        "That single interruption is part of the training.",
    ),
    ("Gamblors", "I will interrupt the rush."),
    ("Intern", "Today's line: Calm mind, cleaner odds."),
    ("Gamblors", "Calm mind, cleaner odds."),
]

DAY_6 = [
    (
        "Intern",
        "Day 6. The advanced teaching begins now: luck is social as much as internal. "
        "Openings often arrive through people before they arrive through numbers.",
    ),
    ("Gamblors", "Then I sharpen the social edge."),
    (
        "Intern",
        "Today you will create one positive micro-interaction on purpose. Start a conversation, "
        "reply with energy, or thank someone properly. Small signals compound.",
    ),
    ("Gamblors", "I will create momentum."),
    (
        "Intern",
        "Most people wait to receive good energy before they give it. That is passive. "
        "You will seed the field first.",
    ),
    ("Gamblors", "Seed the field first."),
    (
        "Intern",
        "Do not force it. Be clean, direct, and real. The goal is not manipulation. "
        "The goal is to become a person around whom favorable motion happens more often.",
    ),
    ("Gamblors", "Favorable motion, Chief."),
    ("Intern", "Today's line: I create conditions that invite opportunity."),
    ("Gamblors", "I create conditions that invite opportunity."),
]

DAY_7 = [
    (
        "Intern",
        "Day 7. You're almost there. Today we train trust in disciplined action. "
        "Not every useful move feels dramatic. Many winning moves feel boring at first.",
    ),
    ("Gamblors", "I trust disciplined action."),
    (
        "Intern",
        "Think of one small action you have been delaying even though you know it is correct. "
        "Send the message. Clean the doc. Finish the setup. Make the call.",
    ),
    ("Gamblors", "I will stop delaying the obvious."),
    (
        "Intern",
        "Delayed correctness becomes self-inflicted bad luck. Timely execution turns into flow.",
    ),
    ("Gamblors", "Timely execution creates flow."),
    (
        "Intern",
        "Your exercise is one overdue move completed today, cleanly and without drama.",
    ),
    ("Gamblors", "One overdue move. Completed."),
    ("Intern", "Today's line: I move when the line is clear."),
    ("Gamblors", "I move when the line is clear."),
]

DAY_8 = [
    (
        "Intern",
        "Day 8. Final day. By now you know the truth: luck is not a costume, and it is not a "
        "single ritual. It is attention, order, calm, openness, and repeated disciplined action.",
    ),
    ("Gamblors", "I understand, Chief."),
    (
        "Intern",
        "Today you integrate the protocol. Keep the mantra. Keep the journal. Keep scanning for "
        "openings. Keep your environment clean. Keep your emotions from hijacking your timing.",
    ),
    ("Gamblors", "I will maintain the protocol."),
    (
        "Intern",
        "You are leaving the training phase, but the real work is repetition. "
        "A statistical anomaly is built by habits that look small to outsiders and obvious in hindsight.",
    ),
    ("Gamblors", "Then I continue the habits."),
    (
        "Intern",
        "Take a final breath and say it clearly: I create my own favorable conditions.",
    ),
    ("Gamblors", "I create my own favorable conditions."),
    ("Intern", "Good. Finish strong. The protocol ends, but the discipline remains."),
    ("Gamblors", "Discipline remains, Chief."),
]

_CONTENT_MAP = {
    1: DAY_1,
    2: DAY_2,
    3: DAY_3,
    4: DAY_4,
    5: DAY_5,
    6: DAY_6,
    7: DAY_7,
    8: DAY_8,
}

_TITLE_MAP = {
    1: "Day 1 - The New Beginning",
    2: "Day 2 - Pattern Recognition",
    3: "Day 3 - Environmental Cleanup",
    4: "Day 4 - Proof Collection",
    5: "Day 5 - Emotional Discipline",
    6: "Day 6 - Social Luck",
    7: "Day 7 - Timely Execution",
    8: "Day 8 - Integration",
}

# Days with a video render as a link out to the tracked /watch page instead
# of the stepped text dialogue above. Video URLs/captions now live in the
# `training_videos` Supabase table (see database/training_videos.py) instead
# of being hardcoded here, so they can be updated without a redeploy.


def get_content(day: int):
    """Return the list of (speaker, message) tuples for the given day."""
    return _CONTENT_MAP.get(day, [])


def get_day_title(day: int) -> str:
    """Return a human-readable title for the given day."""
    return _TITLE_MAP.get(day, f"Day {day}")


def get_day_video(day: int) -> dict | None:
    """Return the {"url", "caption"} mapping for the given day's video, if it has one."""
    return get_training_video(day)


def get_day_banner_path(day: int) -> str | None:
    """Return the local file path for this day's banner image, or None if
    one hasn't been dropped into assets/day_banners/ yet."""
    for ext in _BANNER_EXTS:
        path = os.path.join(_BANNER_DIR, f"day{day}.{ext}")
        if os.path.isfile(path):
            return path
    return None
