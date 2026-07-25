# Centralized in-memory state for the project module
# TODO: Replace with Redis or DB persistence for production scalability

_draft_store: dict[str, list[dict]] = {}
_spec_store: dict[str, dict] = {}
_spec_name_store: dict[str, str] = {}
_base_url_store: dict[str, str] = {}
_gen_meta_store: dict[str, dict] = {}
_run_results_store: dict[str, dict] = {}
_results_store: dict[str, dict] = {}
_generation_meta: dict[str, dict] = {}
_stream_tickets_store: dict[str, dict] = {}
