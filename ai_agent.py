def analyze_student(data):

    quiz_attempted = bool(data.get("quiz_attempted"))
    visual_completed = bool(data.get("visual_completed"))
    mission_attempted = bool(data.get("mission_attempted"))
    teach_back_completed = bool(data.get("teach_back_completed"))

    quiz_score = data.get("quiz_score")
    visualization_score = data.get("visualization_score")
    application_score = data.get("application_score")
    teach_back_score = data.get("teach_back_score")

    quiz_score = float(quiz_score) if quiz_score is not None else None
    visualization_score = (
        float(visualization_score)
        if visualization_score is not None else None
    )
    application_score = (
        float(application_score)
        if application_score is not None else None
    )
    teach_back_score = (
        float(teach_back_score)
        if teach_back_score is not None else None
    )

    # No activity means no fake gap.
    if not any([
        quiz_attempted,
        visual_completed,
        mission_attempted,
        teach_back_completed
    ]):
        return {
            "learning_gap": "No Data Yet",
            "recommended_action": "Start Learning",
            "reason": (
                "The student has not completed any learning activity yet."
            )
        }

    # Detect application problems only after the mission has actually
    # been attempted.
    if (
        mission_attempted
        and application_score is not None
        and application_score < 50
    ):
        return {
            "learning_gap": "Application Gap",
            "recommended_action": "Practice",
            "reason": (
                "The Smart Mission performance indicates that the student "
                "needs more application-based practice."
            )
        }

    # Detect quiz/knowledge problems only after the quiz is attempted.
    if (
        quiz_attempted
        and quiz_score is not None
        and quiz_score < 50
    ):
        return {
            "learning_gap": "Knowledge Gap",
            "recommended_action": "Revision",
            "reason": (
                "The quiz performance indicates that the student needs "
                "to strengthen the topic fundamentals."
            )
        }

    # Teach-back is an understanding check.
    if (
        teach_back_completed
        and teach_back_score is not None
        and teach_back_score < 50
    ):
        return {
            "learning_gap": "Conceptual Gap",
            "recommended_action": "Visual Learning",
            "reason": (
                "The Teach It Back result indicates that the student "
                "needs stronger conceptual understanding."
            )
        }

    # Visual Learning is currently recorded as a completion signal.
    if (
        visual_completed
        and visualization_score is not None
        and visualization_score < 50
    ):
        return {
            "learning_gap": "Visualization Gap",
            "recommended_action": "Visual Learning",
            "reason": (
                "The visual learning assessment indicates that the student "
                "needs additional visual explanation."
            )
        }

    return {
        "learning_gap": "No Major Gap",
        "recommended_action": "Continue",
        "reason": (
            "The completed activities currently show satisfactory "
            "performance. AI will continue monitoring future activity."
        )
    }