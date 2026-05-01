from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Subject, Combination, Paper


@receiver(post_migrate)
def create_default_academic_data(sender, **kwargs):

    if sender.name != 'academic':
        return

    # ===============================
    # SUBJECTS
    # ===============================
    subjects_data = [
        # O-LEVEL
        {"name": "Physics", "code": "PHY_O", "level": "O", "is_core": True},
        {"name": "Chemistry", "code": "CHE_O", "level": "O", "is_core": True},
        {"name": "Biology", "code": "BIO_O", "level": "O", "is_core": True},
        {"name": "Mathematics", "code": "MAT_O", "level": "O", "is_core": True},
        {"name": "Geography", "code": "GEO_O", "level": "O", "is_core": True},
        {"name": "History", "code": "HIS_O", "level": "O", "is_core": True},
        {"name": "English", "code": "ENG_O", "level": "O", "is_core": True},
        {"name": "Kiswahili", "code": "KIS_O", "level": "O", "is_core": True},
        {"name": "Civics", "code": "CIV_O", "level": "O", "is_core": True},

        # A-LEVEL
        {"name": "Physics", "code": "PHY_A", "level": "A", "is_core": True},
        {"name": "Chemistry", "code": "CHE_A", "level": "A", "is_core": True},
        {"name": "Biology", "code": "BIO_A", "level": "A", "is_core": True},
        {"name": "Pure Mathematics", "code": "PMT_A", "level": "A", "is_core": True},
        {"name": "Geography", "code": "GEO_A", "level": "A", "is_core": True},
        {"name": "History", "code": "HIS_A", "level": "A", "is_core": True},
        {"name": "Economics", "code": "ECO_A", "level": "A", "is_core": True},
        {"name": "Computer Science", "code": "CSC_A", "level": "A", "is_core": True},
        {"name": "Kiswahili", "code": "KIS_A", "level": "A", "is_core": True},

        {"name": "General Studies", "code": "GS_A", "level": "A", "is_core": False},
        {"name": "Basic Applied Mathematics", "code": "BAM_A", "level": "A", "is_core": False},
    ]

    for sub in subjects_data:
        Subject.objects.get_or_create(code=sub["code"], defaults=sub)

    # ===============================
    # COMBINATIONS (SAFE ADD ONLY)
    # ===============================
    combinations_data = {
        "PCM": ["PHY_A", "CHE_A", "PMT_A", "GS_A"],
        "PMC": ["PHY_A", "PMT_A", "CSC_A", "GS_A"],
        "PCB": ["PHY_A", "CHE_A", "BIO_A", "GS_A"],
        "EGM": ["ECO_A", "GEO_A", "PMT_A", "GS_A"],
        "CBG": ["CHE_A", "BIO_A", "GEO_A", "GS_A"],
        "HGL": ["HIS_A", "GEO_A", "LAN_A", "GS_A"],
        "HGL": ["HIS_A", "GEO_A", "ENG_A", "GS_A"],
    }

    for combo_name, subject_codes in combinations_data.items():
        combo, _ = Combination.objects.get_or_create(name=combo_name)

        for code in subject_codes:
            subject = Subject.objects.filter(code=code).first()
            if subject:
                combo.subjects.add(subject)   # ✅ SAFE

 # ===============================
# 🔥 CREATE PAPERS (FINAL CLEAN)
# ===============================

def create_papers(subject_code, papers):
    subject = Subject.objects.filter(code=subject_code).first()
    if not subject:
        return

    for p in papers:
        Paper.objects.get_or_create(
            subject=subject,
            paper_number=p["number"],
            defaults={"max_marks": p["marks"]}
        )

# 🔬 SCIENCES (3 papers)
for code in ["PHY_A", "CHE_A", "BIO_A", "CSC_A"]:
    create_papers(code, [
        {"number": 1, "marks": 100},
        {"number": 2, "marks": 100},
        {"number": 3, "marks": 50},
    ])

# 🧮 PURE MATH (2 papers ONLY)
create_papers("PMT_A", [
    {"number": 1, "marks": 100},
    {"number": 2, "marks": 100},
])

# 🌍 ARTS (2 papers)
for code in ["HIS_A", "GEO_A", "ECO_A"]:
    create_papers(code, [
        {"number": 1, "marks": 100},
        {"number": 2, "marks": 100},
    ])

# 🗣 LANGUAGES (2 papers)
for code in ["LAN_A", "KIS_A"]:
    create_papers(code, [
        {"number": 1, "marks": 100},
        {"number": 2, "marks": 100},
    ])

# 📘 COMPULSORY (1 paper)
for code in ["GS_A", "BAM_A"]:
    create_papers(code, [
        {"number": 1, "marks": 100},
    ])