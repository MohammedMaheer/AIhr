from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from main import (
    is_resume_attachment,
    is_resume_related_email,
    is_supported_resume_attachment,
    should_collect_email_attachment,
)
import main


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


def test_gmail_parser_collects_candidate_named_cv_from_resume_related_message():
    message = EmailMessage()
    message["Subject"] = "Application for Accountant"
    message["From"] = "candidate@example.invalid"
    message["Date"] = "Mon, 10 Nov 2026 10:00:00 +0000"
    message.set_content("Please find attached my profile for your review.")
    message.add_attachment(b"%PDF synthetic candidate CV", maintype="application",
                           subtype="pdf", filename="Muhammad Ali.pdf")

    imap = MagicMock()
    imap.__enter__.return_value = imap
    imap.login.return_value = ("OK", [])
    imap.search.return_value = ("OK", [b"1"])
    imap.fetch.return_value = ("OK", [(b"1 (RFC822)", message.as_bytes())])
    with patch.object(main.imaplib, "IMAP4_SSL", return_value=imap):
        results = main.scrape_gmail_attachments("hr@example.invalid", "synthetic", limit=1)

    assert len(results) == 1
    assert results[0]["has_resume_attachment"] is True
    assert results[0]["attachments"][0]["original_filename"] == "Muhammad Ali.pdf"
    assert results[0]["attachments"][0]["content"] == b"%PDF synthetic candidate CV"


def test_gmail_parser_does_not_collect_candidate_named_file_from_unrelated_email():
    message = EmailMessage()
    message["Subject"] = "Company newsletter"
    message["From"] = "news@example.invalid"
    message.set_content("Monthly company announcements.")
    message.add_attachment(b"%PDF unrelated", maintype="application",
                           subtype="pdf", filename="Muhammad Ali.pdf")

    imap = MagicMock()
    imap.__enter__.return_value = imap
    imap.login.return_value = ("OK", [])
    imap.search.return_value = ("OK", [b"1"])
    imap.fetch.return_value = ("OK", [(b"1 (RFC822)", message.as_bytes())])
    with patch.object(main.imaplib, "IMAP4_SSL", return_value=imap):
        results = main.scrape_gmail_attachments("hr@example.invalid", "synthetic", limit=1)

    assert results == []
