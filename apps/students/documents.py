"""
Student document policy (V1).

We keep this in a single place so both Students and Front Office modules
agree on what "missing documents" means.
"""


REQUIRED_DOCUMENT_SETS = {
    # Minimum for basic operations / identity.
    "basic": [
        ("photo", "Profile photo"),
        ("birth_certificate", "Birth certificate"),
    ],
    # A fuller checklist (schools can later configure this per school).
    "all": [
        ("photo", "Profile photo"),
        ("birth_certificate", "Birth certificate"),
        ("aadhar_card", "Aadhar card"),
        ("previous_marksheet", "Previous marksheet"),
        ("transfer_certificate_file", "Transfer certificate"),
        ("caste_certificate", "Caste certificate"),
        ("income_certificate", "Income certificate"),
        ("passport_photo", "Passport photo"),
    ],
}


def required_set_keys():
    return set(REQUIRED_DOCUMENT_SETS.keys())


def required_documents(required="basic"):
    required = (required or "basic").strip().lower()
    if required not in REQUIRED_DOCUMENT_SETS:
        required = "basic"
    return REQUIRED_DOCUMENT_SETS[required]


def missing_documents(student, required="basic"):
    missing = []
    for field, label in required_documents(required):
        if not getattr(student, field, None):
            missing.append(label)
    return missing


def completeness_score(student, required="basic"):
    docs = required_documents(required)
    total = len(docs) or 1
    present = sum(1 for field, _label in docs if getattr(student, field, None))
    return {
        "present": present,
        "total": total,
        "percent": int((present / total) * 100),
    }

