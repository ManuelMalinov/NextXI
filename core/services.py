PRIORITY_VALUES = {
    "high": 0.50,
    "medium": 0.30,
    "low": 0.20,
}

EXPERIENCE_ORDER = {
    "YTH": 0,
    "AM": 1,
    "SEMI": 2,
    "PRO": 3,
}

LOCALITY_NEIGHBOURS = {
    "N": {"NW", "NE", "C"},
    "NE": {"N", "E", "C"},
    "NW": {"N", "W", "C"},
    "E": {"NE", "SE", "C"},
    "SE": {"E", "S", "SW", "C"},
    "SW": {"SE", "S", "W", "C"},
    "W": {"NW", "SW", "C"},
    "S": {"SE", "SW", "C"},
    "C": {"N", "NE", "NW", "E", "SE", "SW", "W", "S"},
}


def normalise_weights(priorities):
    raw = {
        "availability": PRIORITY_VALUES.get(priorities.get("availability", "medium"), 0.30),
        "experience": PRIORITY_VALUES.get(priorities.get("experience", "medium"), 0.30),
        "locality": PRIORITY_VALUES.get(priorities.get("locality", "medium"), 0.30),
    }
    total = sum(raw.values())
    return {key: value / total for key, value in raw.items()}


def availability_similarity(desired, player_value):
    if not desired or desired == "ANY":
        return 1.0
    if desired == player_value:
        return 1.0
    if player_value == "ANY":
        return 0.8
    return 0.0


def experience_similarity(desired, player_value):
    if not desired:
        return 1.0

    desired_rank = EXPERIENCE_ORDER.get(desired)
    player_rank = EXPERIENCE_ORDER.get(player_value)

    if desired_rank is None or player_rank is None:
        return 0.0

    distance = abs(desired_rank - player_rank)

    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.66
    if distance == 2:
        return 0.33
    return 0.0


def locality_similarity(desired, player_value):
    if not desired:
        return 1.0
    if desired == player_value:
        return 1.0
    if player_value in LOCALITY_NEIGHBOURS.get(desired, set()):
        return 0.7
    return 0.3


def availability_label(similarity, filter_value):
    if not filter_value:
        return "Availability not specified"
    if similarity >= 0.95:
        return "Strong availability"
    if similarity >= 0.70:
        return "Flexible availability"
    return "Weaker availability match"


def experience_label(similarity, filter_value):
    if not filter_value:
        return "Experience not specified"
    if similarity >= 0.95:
        return "Exact experience"
    if similarity >= 0.60:
        return "Close experience"
    return "Weaker experience match"


def locality_label(similarity, filter_value):
    if not filter_value:
        return "Locality not specified"
    if similarity >= 0.95:
        return "Nearby locality"
    if similarity >= 0.70:
        return "Reasonably close locality"
    return "Further away locality"


def build_rationale(similarities, filters, weights):
    factors = []

    if filters.get("locality"):
        factors.append({
            "name": "locality",
            "label": locality_label(similarities["locality"], filters.get("locality")),
            "contribution": similarities["locality"] * weights["locality"],
        })

    if filters.get("experience"):
        factors.append({
            "name": "experience",
            "label": experience_label(similarities["experience"], filters.get("experience")),
            "contribution": similarities["experience"] * weights["experience"],
        })

    if filters.get("availability"):
        factors.append({
            "name": "availability",
            "label": availability_label(similarities["availability"], filters.get("availability")),
            "contribution": similarities["availability"] * weights["availability"],
        })

    if not factors:
        return "Position match"

    factors.sort(key=lambda f: f["contribution"], reverse=True)

    return ", ".join(f["label"] for f in factors)


def rank_players(players, filters, priorities):
    weights = normalise_weights(priorities)
    ranked_players = []

    for player in players:
        similarities = {
            "availability": availability_similarity(filters.get("availability"), player.availability_window),
            "experience": experience_similarity(filters.get("experience"), player.experience_level),
            "locality": locality_similarity(filters.get("locality"), player.locality_area),
        }

        score = sum(similarities[factor] * weights[factor] for factor in weights)

        player.match_score = round(score, 3)
        player.match_score_percent = int(round(score * 100))
        player.match_rationale = build_rationale(similarities, filters, weights)

        ranked_players.append(player)

    ranked_players.sort(key=lambda p: (p.match_score, p.user.username.lower()), reverse=True)
    return ranked_players

def rating_explanation(field_name, rating):
    explanations = {
        "positional suitability": {
            "strong": "Your positional suitability was rated as strong, meaning the club felt you understood the demands of the role and applied yourself well in the areas expected.",
            "satisfactory": "Your positional suitability was rated as satisfactory, meaning you showed a reasonable understanding of the role but there is still room to become more consistent.",
            "needs_improvement": "Your positional suitability was rated as needing improvement, meaning some aspects of role awareness and execution require further development.",
            "not_good": "Your positional suitability was rated as not good, meaning the club felt your current fit for this role was below the level required at present.",
        },
        "work rate": {
            "strong": "Your work rate was rated as strong, showing that your effort, intensity, and willingness to compete were viewed positively.",
            "satisfactory": "Your work rate was rated as satisfactory, showing an acceptable level of effort, although greater consistency could improve your impact.",
            "needs_improvement": "Your work rate was rated as needing improvement, meaning the club expected a higher level of energy and sustained effort.",
            "not_good": "Your work rate was rated as not good, meaning the club felt your intensity and contribution without the ball were below expectations.",
        },
        "decision making": {
            "strong": "Your decision making was rated as strong, indicating that your choices in possession and under pressure were generally effective.",
            "satisfactory": "Your decision making was rated as satisfactory, meaning some good choices were made but there were also moments where better options could have been selected.",
            "needs_improvement": "Your decision making was rated as needing improvement, meaning the club felt your choices during key moments need to become more reliable.",
            "not_good": "Your decision making was rated as not good, meaning the club felt your choices often did not meet the level required in the session.",
        },
        "teammate understanding": {
            "strong": "Your understanding with teammates was rated as strong, meaning you linked up well with others and adapted positively to the team context.",
            "satisfactory": "Your understanding with teammates was rated as satisfactory, meaning there were encouraging moments of cooperation but more cohesion could be developed.",
            "needs_improvement": "Your understanding with teammates was rated as needing improvement, meaning the club felt your interactions and coordination within the group could be stronger.",
            "not_good": "Your understanding with teammates was rated as not good, meaning the club felt your combination play and overall chemistry with others were below expectations.",
        },
        "physicality": {
            "strong": "Your physicality was rated as strong, showing that your strength, balance, and overall physical presence matched the demands of the trial well.",
            "satisfactory": "Your physicality was rated as satisfactory, meaning you coped reasonably well physically but there is scope to become more dominant or robust.",
            "needs_improvement": "Your physicality was rated as needing improvement, meaning the club felt you would benefit from improving your physical competitiveness.",
            "not_good": "Your physicality was rated as not good, meaning the club felt the physical side of your performance was below the standard required at this stage.",
        },
    }

    return explanations[field_name][rating]


def generate_feedback_summary(
    attendance,
    positional_suitability="",
    work_rate="",
    decision_making="",
    teammate_understanding="",
    physicality="",
    offer_decision="",
    club_comment=""
):
    if attendance == "did_not_attend":
        summary = (
            "You did not attend the scheduled trial session. "
            "As a result, the club was unable to assess your performance during the planned session "
            "and will not be offering you a place in the team at this time."
        )
        if club_comment:
            summary += f" Additional note from the club: {club_comment.strip()}"
        return summary

    parts = [
        "You attended the trial and the club completed a structured review of your performance.",
        rating_explanation("positional suitability", positional_suitability),
        rating_explanation("work rate", work_rate),
        rating_explanation("decision making", decision_making),
        rating_explanation("teammate understanding", teammate_understanding),
        rating_explanation("physicality", physicality),
    ]

    if offer_decision == "yes":
        parts.append(
            "Based on the overall assessment of your trial, the club would like to offer you a place in the team."
        )
    else:
        parts.append(
            "Based on the overall assessment of your trial, the club will not be offering you a place in the team at this time."
        )

    if club_comment:
        parts.append(f"Additional note from the club: {club_comment.strip()}")

    return " ".join(parts)