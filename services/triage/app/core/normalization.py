"""Analysis parser is tolerant of malformed HTML; rendering always sanitizes."""
from __future__ import annotations
import html
import re
from bs4 import BeautifulSoup
import bleach

MATH_TAGS = "math mrow mn mi mo mfrac msqrt mroot msub msup msubsup munder mover munderover mtable mtr mtd mstyle mtext mspace menclose mfenced mmultiscripts mprescripts mnone semantics annotation".split()
HTML_TAGS = "h1 h2 h3 h4 p br b strong i em span div sup sub ul ol li table tr td th img blockquote".split()
ALLOWED_ATTRS = {"math": ["xmlns", "display"], "mspace": ["width", "height", "depth", "linebreak"], "mo": ["stretchy", "fence", "form", "lspace", "rspace"], "mi": ["mathvariant"], "mn": ["mathvariant"], "mstyle": ["displaystyle", "mathsize", "scriptlevel"], "mtd": ["columnalign"], "img": ["src", "alt", "width", "height"]}
# No remote images and no CSS/style attributes in stored content; external images need a trusted proxy.

def sanitize_markup(raw: str) -> str:
    cleaned = bleach.clean(raw or "", tags=HTML_TAGS + MATH_TAGS, attributes=ALLOWED_ATTRS, protocols=["https", "http"], strip=True)
    # remove external images entirely: image URLs have not been approved as safe first-party assets
    cleaned = re.sub(r"<img\b[^>]*>", "", cleaned, flags=re.I)
    return cleaned


def plain_text(raw: str) -> str:
    soup = BeautifulSoup(raw or "", "html5lib")
    for bad in soup(["script", "style", "iframe"]):
        bad.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def html_options(raw: str) -> dict[str, str]:
    """A conservative extraction for labels in mixed HTML/MathML.
    Returns extracted strings, never fabricates an option.
    """
    text = plain_text(raw)
    matches = list(re.finditer(r"\(([A-D])\)", text, re.I))
    found: dict[str, str] = {}
    for i, match in enumerate(matches):
        label = match.group(1).upper()
        if label in found:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        found[label] = text[match.end():end].strip()
    return found


def stem_only(raw: str) -> str:
    text = plain_text(raw)
    match = re.search(r"\([A-D]\)", text)
    return text[:match.start()].strip() if match else text


def normalized_question(q: dict) -> dict:
    body = q[q["questionType"]]
    return {
        "_id": q["_id"], "questionType": q["questionType"], "subject": q.get("subject"),
        "chapter": q.get("chapter"), "question_text": stem_only(body.get("question", "")),
        "options": html_options(body.get("question", "")), "question_html": body.get("question", ""),
        "solution_text": plain_text(body.get("solution", "")), "solution_html": body.get("solution", ""),
        "answer": body.get("answer"), "quesImages": body.get("quesImages", []),
        "solutionImages": body.get("solutionImages", []),
    }
