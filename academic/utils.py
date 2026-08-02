from collections import defaultdict

from .models import StudentMark, Subject


def get_olevel_grade(marks):
    if marks >= 75:
        return 'A', 1
    if marks >= 65:
        return 'B', 2
    if marks >= 45:
        return 'C', 3
    if marks >= 30:
        return 'D', 4
    return 'F', 5


def get_alevel_grade(marks):
    if marks >= 80:
        return 'A', 1
    if marks >= 70:
        return 'B', 2
    if marks >= 60:
        return 'C', 3
    if marks >= 50:
        return 'D', 4
    if marks >= 40:
        return 'E', 5
    if marks >= 35:
        return 'S', 6
    return 'F', 7


def calculate_olevel_division(points):
    if 7 <= points <= 17:
        return "Division I"
    if 18 <= points <= 21:
        return "Division II"
    if 22 <= points <= 25:
        return "Division III"
    if 26 <= points <= 33:
        return "Division IV"
    return "Division 0"


def calculate_alevel_division(points):
    if 3 <= points <= 9:
        return "Division I"
    if 10 <= points <= 12:
        return "Division II"
    if 13 <= points <= 15:
        return "Division III"
    if 16 <= points <= 18:
        return "Division IV"
    return "Division 0"


def calculate_student_result(student, exam):
    marks_qs = StudentMark.objects.filter(
        student=student,
        exam=exam
    ).select_related('subject', 'paper')

    subject_totals = defaultdict(float)
    subject_max = defaultdict(float)
    subject_papers = defaultdict(list)

    for mark in marks_qs:
        if mark.is_absent:
            subject_totals[mark.subject_id] = "ABS"
            subject_papers[mark.subject_id].append({
                "paper_number": mark.paper.paper_number if mark.paper else None,
                "marks": "ABS"
            })
            continue

        subject_totals[mark.subject_id] += mark.marks
        subject_max[mark.subject_id] += mark.paper.max_marks if mark.paper else 100
        subject_papers[mark.subject_id].append({
            "paper_number": mark.paper.paper_number if mark.paper else None,
            "marks": round(mark.marks, 2)
        })

    results = []
    subjects_with_marks = Subject.objects.filter(id__in=subject_totals.keys())

    for subject in subjects_with_marks:
        subject_id = subject.id
        total_marks = subject_totals.get(subject_id)

        if total_marks == "ABS":
            results.append({
                "subject": subject,
                "grade": "ABS",
                "points": 7,
                "is_core": subject.is_core,
                "total_marks": None,
                "max_marks": round(subject_max.get(subject_id, 0), 2),
                "percentage": None,
                "papers": sorted(subject_papers.get(subject_id, []), key=lambda x: x['paper_number'] or 0),
            })
            continue

        max_marks = subject_max[subject_id]
        percentage = (total_marks / max_marks) * 100 if max_marks else 0

        if exam.level == 'O':
            grade, points = get_olevel_grade(percentage)
        else:
            grade, points = get_alevel_grade(percentage)

        results.append({
            "subject": subject,
            "grade": grade,
            "points": points,
            "is_core": subject.is_core,
            "total_marks": round(total_marks, 2),
            "max_marks": round(max_marks, 2),
            "percentage": round(percentage, 2),
            "papers": sorted(subject_papers.get(subject_id, []), key=lambda x: x['paper_number'] or 0),
        })

    required_subjects = 7 if exam.level == 'O' else 3
    points_list = sorted([r["points"] for r in results if r["points"] > 0])
    counted_points = points_list[:required_subjects]
    is_complete = len(points_list) >= required_subjects
    total_points = sum(counted_points)
    
    marked_results = [r for r in results if r["total_marks"] is not None]
    total_marks_sum = sum(r["total_marks"] for r in marked_results)
    # Average over subjects actually marked — dividing by len(results) would
    # understate it by counting absent subjects (which contribute 0) in the denominator.
    average_marks = total_marks_sum / len(marked_results) if marked_results else 0

    if not is_complete:
        division = "Incomplete"
    elif exam.level == 'O':
        division = calculate_olevel_division(total_points)
    else:
        division = calculate_alevel_division(total_points)

    return {
        "student": student,
        "exam": exam,
        "subjects": results,
        "total_marks_sum": round(total_marks_sum, 2),
        "average_marks": round(average_marks, 2),
        "total_points": total_points,
        "division": division,
        "required_subjects": required_subjects,
        "counted_subjects": len(counted_points),
        "attempted_subjects": len(points_list),
        "is_complete": is_complete,
    }


def rank_students(students, exam):
    results = []

    for student in students:
        res = calculate_student_result(student, exam)

        if res["total_points"] == 0 and not res["subjects"]:
            continue

        results.append({
            "student": student,
            "total_marks_sum": res["total_marks_sum"],
            "average_marks": res["average_marks"],
            "points": res["total_points"],
            "division": res["division"],
            "is_complete": res["is_complete"],
            # Carry the full per-subject breakdown so callers don't have to
            # call calculate_student_result() again for the same student/exam.
            "subjects": res["subjects"],
        })

    # Sort: Complete results first, then Highest Total Marks, then Best (lowest) Points
    ranked = sorted(results, key=lambda x: (not x["is_complete"], -x["total_marks_sum"], x["points"]))

    current_position = 1
    for i, r in enumerate(ranked):
        if i > 0 and r["points"] == ranked[i - 1]["points"] and r["is_complete"] == ranked[i - 1]["is_complete"]:
            r["position"] = ranked[i - 1]["position"]
        else:
            r["position"] = current_position
        current_position += 1

    return ranked
