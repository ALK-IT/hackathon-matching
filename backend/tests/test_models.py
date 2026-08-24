from app.enums import ExperienceLevel, PreferredRole
from app.models import Submission


def test_submission_can_be_instantiated() -> None:
    submission = Submission(
        full_name="Jan Kowalski",
        email="jan.kowalski@example.com",
        skills=["python", "react"],
        experience_level=ExperienceLevel.INTERMEDIATE,
        preferred_role=PreferredRole.BACKEND,
        availability=True,
    )

    assert submission.full_name == "Jan Kowalski"
    assert submission.email == "jan.kowalski@example.com"
    assert submission.skills == ["python", "react"]
    assert submission.experience_level is ExperienceLevel.INTERMEDIATE
    assert submission.preferred_role is PreferredRole.BACKEND
    assert submission.availability is True


def test_enums_serialize_to_their_values() -> None:
    """Baza i API operują na wartościach ("backend"), nie nazwach ("BACKEND").

    Gdyby ktoś zamienił `StrEnum` na zwykły `Enum`, w bazie zaczęłyby lądować
    nazwy, a API dalej przyjmowałoby wartości - rozjazd wyszedłby dopiero na
    produkcji.
    """
    assert str(PreferredRole.BACKEND) == "backend"
    assert str(ExperienceLevel.ADVANCED) == "advanced"


def test_profile_columns_have_database_level_check() -> None:
    """Zbiór dopuszczalnych wartości pilnuje też baza, nie tylko pydantic."""
    constraints = {constraint.name for constraint in Submission.__table__.constraints}

    assert {"experience_level", "preferred_role"} <= constraints
