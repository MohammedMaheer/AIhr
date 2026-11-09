"""Conservative local ingestion gates; no provider calls or generated CV facts."""
import re


def normalize_text(text):
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text or '')
    return '\n'.join(line.rstrip() for line in text.replace('\r\n', '\n').replace('\r', '\n').splitlines()).strip()


def review_text(text, filename):
    text = normalize_text(text)
    words = re.findall(r'\w+', text, re.UNICODE)
    if len(text) > 80_000:
        return 'review_oversized_text'
    if len(text) < 200 or len(words) < 30:
        return 'review_insufficient_text'
    if sum(c.isalpha() for c in text) / len(text) < 0.35 or '\ufffd' in text:
        return 'review_text_quality'
    supporting = re.search(r'offer[ _-]*letter|letter[ _-]*of[ _-]*experience|degree|certificate|our[ _-]*clients|portfolio', filename, re.I)
    if supporting:
        return 'review_supporting_document'
    patterns = (
        r'\b(?:experience|employment|work history|career history|professional background)\b',
        r'\b(?:education|qualification|academic|bachelor|master|university|diploma)\b',
        r'\b(?:skills|competenc(?:y|ies)|technologies|technical expertise|expertise)\b',
        r'\b(?:professional summary|career objective|profile|curriculum vitae|resume|biodata)\b',
    )
    sections = sum(bool(re.search(pattern, text, re.I)) for pattern in patterns)
    if sections < 2:
        return 'review_document_type'
    return 'accepted'


def acceptable_ocr(confidences):
    values = [float(value) for value in confidences if float(value) >= 0]
    return bool(values) and sum(values) / len(values) >= 80 and sum(value < 50 for value in values) / len(values) <= 0.2
