"""The three asks from the regulatory team, as ready-made review templates."""

PRESETS = [
    {
        "id": "cmc_excipients",
        "name": "CMC excipient grades vs current spec",
        "doc_filter": {"doc_type": "cmc", "query": "excipient grade"},
        "reference": "spec",
        "questions": [
            {"key": "excipient_grades", "answer_type": "list",
             "prompt": "List every excipient with the grade used, formatted 'Excipient: grade'."},
            {"key": "grade_justification", "answer_type": "text",
             "prompt": "What justification is given for the choice of excipient grade?"},
            {"key": "guidance_cited", "answer_type": "list",
             "prompt": "Which regulatory guidance documents or compendial monographs are cited?"},
            # Comparison first (schema order = generation order) so the yes/no is reasoned, and reviewable.
            {"key": "spec_comparison", "answer_type": "list",
             "prompt": "For each excipient, compare the DOCUMENT grade with the approved grade for this product in "
                       "the REFERENCE, formatted 'Excipient: document grade vs spec grade: consistent|conflict'. A "
                       "document grade that only adds detail (e.g. a brand name or source) is consistent; a different "
                       "grade number, physical form or hydrate is a conflict. Cite both documents."},
            {"key": "contradicts_spec", "answer_type": "boolean",
             "prompt": "Based on spec_comparison, is any excipient grade in conflict with the REFERENCE "
                       "specification? Answer yes only if at least one comparison is a conflict."},
        ],
    },
    {
        "id": "ha_commitments",
        "name": "Health authority commitments",
        "doc_filter": {"doc_type": "ha_letter", "query": "commitment due date"},
        "questions": [
            {"key": "commitment", "answer_type": "text", "prompt": "What commitment did the applicant make?"},
            {"key": "due_date", "answer_type": "date", "prompt": "What is the due date of the commitment (YYYY-MM-DD)?"},
            {"key": "met", "answer_type": "boolean",
             "prompt": "Does the document state that the commitment has already been met?"},
            {"key": "owner", "answer_type": "text", "prompt": "Which named person owns or is the contact for this commitment?"},
        ],
    },
    {
        "id": "stability_protocols",
        "name": "Stability protocol review",
        "doc_filter": {"doc_type": "stability_protocol", "query": "stability storage timepoints"},
        "questions": [
            {"key": "storage_condition", "answer_type": "text", "prompt": "What storage conditions are used?"},
            {"key": "timepoints", "answer_type": "text", "prompt": "What are the testing timepoints?"},
            {"key": "acceptance_criteria", "answer_type": "list", "prompt": "List the acceptance criteria."},
            {"key": "deviations", "answer_type": "text", "prompt": "What deviations are recorded, if any?"},
            {"key": "bracketing_justification", "answer_type": "text",
             "prompt": "Is bracketing applied, and what is the justification?"},
            {"key": "post_approval_commitment", "answer_type": "text", "prompt": "What is the post-approval stability commitment?"},
        ],
    },
]
