from app.models import Submission


def test_submission_can_be_instantiated() -> None:
    submission = Submission(
        full_name="Jan Kowalski",
        email="jan.kowalski@example.com",
        skills="python,react",
    )

    assert submission.full_name == "Jan Kowalski"
    assert submission.email == "jan.kowalski@example.com"
    assert submission.skills == "python,react"
