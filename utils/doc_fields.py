"""
Which optional fields the entry forms show for each Document Type.

Stored in config as doc_type_hidden_fields: {document type: [sheet column, ...]}
and edited from Configuration -> Document Types.
"""

# Sheet column -> short label for the Configuration table. Fields not listed here are always on the form.
OPTIONAL_FIELDS = {
    "Party_Name 1 Partners": "Partners",
    "Party_Name 2":          "Party 2",
    "Garvi_Application_ID":  "GARVI No",
    "Inedex_Application_No": "Index App No",
    "Search_No":             "Search No",
    "Index_No":              "Index No",
    "Title_Status":          "Title Status",
    "Remark":                "Remark",
}


def hidden_fields(config: dict, doc_type) -> set:
    rules = (config or {}).get("doc_type_hidden_fields") or {}
    return set(rules.get(str(doc_type or "").strip()) or [])
