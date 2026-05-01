from .models import StudentMark, Subject
from collections import defaultdict


# ===============================
# O-LEVEL GRADING (NECTA)
# ===============================
def get_olevel_grade(marks):
    if marks >= 75:
        return 'A', 1
    elif marks >= 65:
        return 'B', 2
    elif marks >= 45:
        return 'C', 3
    elif marks >= 30:
        return 'D', 4
    else:
        return 'F', 5


# ===============================
# A-LEVEL GRADING (NECTA)
# ===============================
def get_alevel_grade(marks):
    if marks >= 80:
        return 'A', 1
    elif marks >= 70:
        return 'B', 2
    elif marks >= 60:
        return 'C', 3
    elif marks >= 50:
        return 'D', 4
    elif marks >= 40:
        return 'E', 5
    elif marks >= 35:
        return 'S', 6
    else:
        return 'F', 7


# ===============================
# O-LEVEL DIVISION
# ===============================
def calculate_olevel_division(points):
    if 7 <= points <= 17:
        return "Division I"
    elif 18 <= points <= 21:
        return "Division II"
    elif 22 <= points <= 25:
        return "Division III"
    elif 26 <= points <= 33:
        return "Division IV"
    else:
        return "Division 0"


# ===============================
# A-LEVEL DIVISION
# ===============================
def calculate_alevel_division(points):
    if 3 <= points <= 9:
        return "Division I"
    elif 10 <= points <= 12:
        return "Division II"
    elif 13 <= points <= 15:
        return "Division III"
    elif 16 <= points <= 18:
        return "Division IV"
    else:
        return "Division 0"


# ===============================
# 🔥 MAIN RESULT CALCULATOR
# ===============================
from collections import defaultdict
from .models import StudentMark, Subject

def calculate_student_result(student, exam):

    marks_qs = StudentMark.objects.filter(
        student=student,
        exam=exam
    ).select_related('subject', 'paper')

    subject_totals = defaultdict(float)
    subject_max = defaultdict(float)

    # ===============================
    # COLLECT MARKS
    # ===============================
    for mark in marks_qs:

        if mark.is_absent:
            subject_totals[mark.subject.id] = "ABS"
            continue

        subject_totals[mark.subject.id] += mark.marks

        if mark.paper:
            subject_max[mark.subject.id] += mark.paper.max_marks
        else:
            subject_max[mark.subject.id] += 100

    results = []

    # ===============================
    # GET ALL SUBJECTS (IMPORTANT FIX)
    # ===============================
    # ===============================
# 🎯 USE ONLY SUBJECTS WITH MARKS (FIXED)
# ===============================
    subjects_with_marks = Subject.objects.filter(
       id__in=subject_totals.keys()
    )

    for subject in subjects_with_marks:
        subject_id = subject.id
        total_marks = subject_totals.get(subject_id, None)

        # ❌ NO MARKS
        if total_marks is None:
            results.append({
                "subject": subject,
                "grade": "-",
                "points": 0,
                "is_core": subject.is_core
            })
            continue

        # 🚫 ABSENT
        if total_marks == "ABS":
            results.append({
                "subject": subject,
                "grade": "ABS",
                "points": 7,
                "is_core": subject.is_core
            })
            continue

        max_marks = subject_max[subject_id]
        percentage = (total_marks / max_marks) * 100 if max_marks else 0

        # GRADE
        if exam.level == 'O':
            if percentage >= 75:
                grade, points = 'A', 1
            elif percentage >= 65:
                grade, points = 'B', 2
            elif percentage >= 45:
                grade, points = 'C', 3
            elif percentage >= 30:
                grade, points = 'D', 4
            else:
                grade, points = 'F', 5
        else:
            if percentage >= 80:
                grade, points = 'A', 1
            elif percentage >= 70:
                grade, points = 'B', 2
            elif percentage >= 60:
                grade, points = 'C', 3
            elif percentage >= 50:
                grade, points = 'D', 4
            elif percentage >= 40:
                grade, points = 'E', 5
            elif percentage >= 35:
                grade, points = 'S', 6
            else:
                grade, points = 'F', 7

        results.append({
            "subject": subject,
            "grade": grade,
            "points": points,
            "is_core": subject.is_core
        })

    # ===============================
    # DIVISION (FIXED FOR BOTH LEVELS)
    # ===============================
    points_list = sorted([r["points"] for r in results if r["points"] > 0])
    best = points_list[:7] if exam.level == 'O' else points_list[:3]

    total_points = sum(best)

    if exam.level == 'O':
        if total_points <= 17:
            division = "Division I"
        elif total_points <= 21:
            division = "Division II"
        elif total_points <= 25:
            division = "Division III"
        elif total_points <= 33:
            division = "Division IV"
        else:
            division = "Division 0"
    else:  # A-Level
        if total_points <= 9:
            division = "Division I"
        elif total_points <= 12:
            division = "Division II"
        elif total_points <= 15:
            division = "Division III"
        elif total_points <= 18:
            division = "Division IV"
        else:
            division = "Division 0"

    # Return the result dictionary
    return {
        "student": student,
        "exam": exam,
        "subjects": results,
        "total_points": total_points,
        "division": division
    }
# ===============================
# 🏆 RANKING ENGINE (FIXED)
# ===============================
def rank_students(students, exam):
    """
    Rank students based on total points
    Lower points = better rank (Division I has lowest points)
    """
    results = []
    
    for student in students:
        res = calculate_student_result(student, exam)
        
        # Skip students with no results
        if res["total_points"] == 0 and not res["subjects"]:
            continue
            
        results.append({
            "student": student,
            "points": res["total_points"],
            "division": res["division"]
        })
    
    # Sort by points (ascending = better), then by division if points are equal
    ranked = sorted(results, key=lambda x: (x["points"], x["division"]))
    
    # Assign positions
    current_position = 1
    for i, r in enumerate(ranked):
        if i > 0 and r["points"] == ranked[i-1]["points"]:
            r["position"] = ranked[i-1]["position"]  # Same position for ties
        else:
            r["position"] = current_position
        current_position += 1
    
    return ranked