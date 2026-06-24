from main import (
    is_resume_attachment,
    is_resume_related_email,
    is_supported_resume_attachment,
    should_collect_email_attachment,
)


def test_candidate_named_pdf_is_supported_but_not_filename_resume_keyword():
    assert is_supported_resume_attachment("Muhammad Ali.pdf")
    assert not is_resume_attachment("Muhammad Ali.pdf")


def test_candidate_named_pdf_is_collected_when_email_context_is_resume_related():
    assert is_resume_related_email(
        "Application for Accountant",
        "Please find attached my profile for your review.",
    )
    assert should_collect_email_attachment("Muhammad Ali.pdf", True)


def test_unsupported_attachment_is_not_collected_even_with_resume_context():
    assert not is_supported_resume_attachment("portfolio.zip")
    assert not should_collect_email_attachment("portfolio.zip", True)


def test_keyword_filename_is_collected_even_without_email_context():
    assert is_resume_attachment("john_cv.docx")
    assert should_collect_email_attachment("john_cv.docx", False)
