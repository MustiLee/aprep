"""Seed AP subjects data into the database."""

import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from src.core.database import SessionLocal
from src.models.db_models import APSubject


def seed_ap_subjects():
    """Seed initial AP subjects."""
    db = SessionLocal()

    ap_subjects = [
        {
            "name": "AP Calculus AB",
            "code": "CALC_AB",
            "description": "Limits, derivatives, integrals, and the Fundamental Theorem of Calculus",
            "difficulty_level": 4,
            "topics_count": 8,
            "exam_format": {
                "mcq_count": 45,
                "mcq_time_minutes": 105,
                "frq_count": 6,
                "frq_time_minutes": 90,
            },
        },
        {
            "name": "AP Calculus BC",
            "code": "CALC_BC",
            "description": "All AB topics plus parametric equations, polar coordinates, vector-valued functions, and series",
            "difficulty_level": 5,
            "topics_count": 10,
            "exam_format": {
                "mcq_count": 45,
                "mcq_time_minutes": 105,
                "frq_count": 6,
                "frq_time_minutes": 90,
            },
        },
        {
            "name": "AP Statistics",
            "code": "STATS",
            "description": "Exploring data, sampling, experimentation, probability, and statistical inference",
            "difficulty_level": 3,
            "topics_count": 9,
            "exam_format": {
                "mcq_count": 40,
                "mcq_time_minutes": 90,
                "frq_count": 6,
                "frq_time_minutes": 90,
            },
        },
        {
            "name": "AP Physics 1",
            "code": "PHYSICS_1",
            "description": "Algebra-based physics: kinematics, dynamics, circular motion, energy, momentum, simple harmonic motion, waves",
            "difficulty_level": 4,
            "topics_count": 7,
            "exam_format": {
                "mcq_count": 50,
                "mcq_time_minutes": 90,
                "frq_count": 5,
                "frq_time_minutes": 90,
            },
        },
        {
            "name": "AP Physics C: Mechanics",
            "code": "PHYSICS_C_MECH",
            "description": "Calculus-based mechanics: kinematics, Newton's laws, energy, momentum, rotation, oscillations",
            "difficulty_level": 5,
            "topics_count": 7,
            "exam_format": {
                "mcq_count": 35,
                "mcq_time_minutes": 45,
                "frq_count": 3,
                "frq_time_minutes": 45,
            },
        },
        {
            "name": "AP Chemistry",
            "code": "CHEMISTRY",
            "description": "Atomic structure, intermolecular forces, chemical reactions, kinetics, thermodynamics, equilibrium",
            "difficulty_level": 4,
            "topics_count": 9,
            "exam_format": {
                "mcq_count": 60,
                "mcq_time_minutes": 90,
                "frq_count": 7,
                "frq_time_minutes": 105,
            },
        },
        {
            "name": "AP Biology",
            "code": "BIOLOGY",
            "description": "Evolution, cellular processes, genetics, information transfer, ecology, and interactions",
            "difficulty_level": 4,
            "topics_count": 8,
            "exam_format": {
                "mcq_count": 60,
                "mcq_time_minutes": 90,
                "frq_count": 6,
                "frq_time_minutes": 90,
            },
        },
        {
            "name": "AP Computer Science A",
            "code": "CSA",
            "description": "Object-oriented programming in Java: classes, algorithms, data structures, program design",
            "difficulty_level": 3,
            "topics_count": 10,
            "exam_format": {
                "mcq_count": 40,
                "mcq_time_minutes": 90,
                "frq_count": 4,
                "frq_time_minutes": 90,
            },
        },
        {
            "name": "AP Computer Science Principles",
            "code": "CSP",
            "description": "Computational thinking, algorithms, programming, internet, global impact of computing",
            "difficulty_level": 2,
            "topics_count": 7,
            "exam_format": {
                "mcq_count": 70,
                "mcq_time_minutes": 120,
                "frq_count": 0,
                "frq_time_minutes": 0,
            },
        },
        {
            "name": "AP English Language",
            "code": "ENG_LANG",
            "description": "Rhetorical analysis, argument, synthesis writing",
            "difficulty_level": 3,
            "topics_count": 9,
            "exam_format": {
                "mcq_count": 45,
                "mcq_time_minutes": 60,
                "frq_count": 3,
                "frq_time_minutes": 135,
            },
        },
        {
            "name": "AP English Literature",
            "code": "ENG_LIT",
            "description": "Literary analysis, poetry, prose, and drama analysis",
            "difficulty_level": 4,
            "topics_count": 9,
            "exam_format": {
                "mcq_count": 55,
                "mcq_time_minutes": 60,
                "frq_count": 3,
                "frq_time_minutes": 120,
            },
        },
        {
            "name": "AP US History",
            "code": "APUSH",
            "description": "American history from pre-Columbian to present day",
            "difficulty_level": 4,
            "topics_count": 9,
            "exam_format": {
                "mcq_count": 55,
                "mcq_time_minutes": 55,
                "frq_count": 4,
                "frq_time_minutes": 100,
            },
        },
        {
            "name": "AP World History",
            "code": "WORLD_HIST",
            "description": "World history from 1200 CE to present",
            "difficulty_level": 4,
            "topics_count": 9,
            "exam_format": {
                "mcq_count": 55,
                "mcq_time_minutes": 55,
                "frq_count": 3,
                "frq_time_minutes": 100,
            },
        },
        {
            "name": "AP Macroeconomics",
            "code": "MACRO",
            "description": "Economic systems, national income, inflation, unemployment, fiscal and monetary policy",
            "difficulty_level": 3,
            "topics_count": 6,
            "exam_format": {
                "mcq_count": 60,
                "mcq_time_minutes": 70,
                "frq_count": 3,
                "frq_time_minutes": 60,
            },
        },
        {
            "name": "AP Microeconomics",
            "code": "MICRO",
            "description": "Supply and demand, market structures, factor markets, market failure, role of government",
            "difficulty_level": 3,
            "topics_count": 6,
            "exam_format": {
                "mcq_count": 60,
                "mcq_time_minutes": 70,
                "frq_count": 3,
                "frq_time_minutes": 60,
            },
        },
    ]

    try:
        # Check if subjects already exist
        existing_count = db.query(APSubject).count()
        if existing_count > 0:
            print(f"Database already has {existing_count} subjects. Skipping seed.")
            return

        # Add subjects
        for subject_data in ap_subjects:
            subject = APSubject(
                id=uuid4(),
                name=subject_data["name"],
                code=subject_data["code"],
                description=subject_data["description"],
                difficulty_level=subject_data["difficulty_level"],
                topics_count=subject_data["topics_count"],
                exam_format=subject_data["exam_format"],
                is_active=True,
            )
            db.add(subject)

        db.commit()
        print(f"Successfully seeded {len(ap_subjects)} AP subjects!")

        # Print summary
        for subject in ap_subjects:
            print(f"  - {subject['name']} ({subject['code']})")

    except Exception as e:
        print(f"Error seeding AP subjects: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_ap_subjects()
