"""Tests for oetp_bridge.py."""
import copy
import time
import pytest
from oetp_bridge import valichord_source_entry, inject_into_disclosure, minimal_disclosure

# --- fixtures ---

ROUND_AI_VALIDATOR = {
    'outcome_type': 'Reproduced',
    'agreement_level': 'ExactMatch',
    'validator_count': 3,
    'record_url': 'http://132.145.34.27:3001/record?hash=uhC8kABC',
    'harmony_record_hash': 'uhC8kABC',
}

ROUND_DEMO_RUNNER = {
    'outcome': 'Reproduced',
    'agreement_level': 'WithinTolerance',
    'validator_count': 5,
    'record_url': 'http://132.145.34.27:3001/record?hash=uhC8kDEF',
    'harmony_record_hash': 'uhC8kDEF',
}

EXISTING_DISCLOSURE = {
    'schema': {
        'name': 'Open Ethics Transparency Protocol',
        'version': '0.9.3 RFC',
        'integrity': 'abc123',
    },
    'snapshot': {
        'product': {'url': 'example.com'},
        'timestamp': 1700000000,
        'generator': {
            'name': 'Open Ethics',
            'alias': 'oe',
            'type': 'root',
            'website': 'https://openethics.ai',
        },
        'label': {
            'data':     {'type': 'open',       'practice': ''},
            'source':   {'type': 'open',       'practice': ''},
            'decision': {'type': 'restricted', 'practice': ''},
        },
    },
}


# --- valichord_source_entry ---

class TestValiChordSourceEntry:
    def test_type_field(self):
        entry = valichord_source_entry(ROUND_AI_VALIDATOR)
        assert entry['type'] == 'ValiChord Reproducibility Attestation'

    def test_url_is_record_url(self):
        entry = valichord_source_entry(ROUND_AI_VALIDATOR)
        assert entry['url'] == ROUND_AI_VALIDATOR['record_url']

    def test_comments_contains_outcome(self):
        entry = valichord_source_entry(ROUND_AI_VALIDATOR)
        assert 'Reproduced' in entry['comments']

    def test_comments_contains_agreement(self):
        entry = valichord_source_entry(ROUND_AI_VALIDATOR)
        assert 'ExactMatch' in entry['comments']

    def test_comments_contains_validator_fraction(self):
        entry = valichord_source_entry(ROUND_AI_VALIDATOR)
        assert '3/3' in entry['comments']

    def test_comments_contains_harmony_hash(self):
        entry = valichord_source_entry(ROUND_AI_VALIDATOR)
        assert ROUND_AI_VALIDATOR['harmony_record_hash'] in entry['comments']

    def test_required_oetp_source_keys(self):
        entry = valichord_source_entry(ROUND_AI_VALIDATOR)
        assert {'type', 'url', 'comments'} <= entry.keys()

    def test_outcome_key_fallback_to_outcome(self):
        # demo_runner uses 'outcome'; ai_validator uses 'outcome_type'
        entry = valichord_source_entry(ROUND_DEMO_RUNNER)
        assert 'Reproduced' in entry['comments']

    def test_outcome_type_takes_precedence(self):
        # if both keys present, outcome_type wins
        result = {**ROUND_DEMO_RUNNER, 'outcome_type': 'FailedToReproduce'}
        entry = valichord_source_entry(result)
        assert 'FailedToReproduce' in entry['comments']
        assert 'Reproduced' not in entry['comments']

    def test_five_validators(self):
        entry = valichord_source_entry(ROUND_DEMO_RUNNER)
        assert '5/5' in entry['comments']

    def test_missing_optional_fields_do_not_raise(self):
        entry = valichord_source_entry({})
        assert entry['type'] == 'ValiChord Reproducibility Attestation'


# --- inject_into_disclosure ---

class TestInjectIntoDisclosure:
    def test_source_entry_appended(self):
        result = inject_into_disclosure(EXISTING_DISCLOSURE, ROUND_AI_VALIDATOR)
        sources = result['snapshot']['processing']['source']
        assert len(sources) == 1
        assert sources[0]['type'] == 'ValiChord Reproducibility Attestation'

    def test_existing_source_list_preserved(self):
        d = copy.deepcopy(EXISTING_DISCLOSURE)
        d['snapshot']['processing'] = {
            'source': [{'type': 'Code Repository', 'url': 'https://github.com/example'}]
        }
        result = inject_into_disclosure(d, ROUND_AI_VALIDATOR)
        sources = result['snapshot']['processing']['source']
        assert len(sources) == 2
        assert sources[0]['type'] == 'Code Repository'
        assert sources[1]['type'] == 'ValiChord Reproducibility Attestation'

    def test_does_not_mutate_input(self):
        original = copy.deepcopy(EXISTING_DISCLOSURE)
        inject_into_disclosure(EXISTING_DISCLOSURE, ROUND_AI_VALIDATOR)
        assert EXISTING_DISCLOSURE == original

    def test_creates_processing_block_if_absent(self):
        result = inject_into_disclosure(EXISTING_DISCLOSURE, ROUND_AI_VALIDATOR)
        assert 'processing' in result['snapshot']
        assert 'source' in result['snapshot']['processing']

    def test_creates_source_list_if_processing_exists_without_it(self):
        d = copy.deepcopy(EXISTING_DISCLOSURE)
        d['snapshot']['processing'] = {}
        result = inject_into_disclosure(d, ROUND_AI_VALIDATOR)
        assert isinstance(result['snapshot']['processing']['source'], list)

    def test_schema_block_unchanged(self):
        result = inject_into_disclosure(EXISTING_DISCLOSURE, ROUND_AI_VALIDATOR)
        assert result['schema'] == EXISTING_DISCLOSURE['schema']

    def test_label_block_unchanged(self):
        result = inject_into_disclosure(EXISTING_DISCLOSURE, ROUND_AI_VALIDATOR)
        assert result['snapshot']['label'] == EXISTING_DISCLOSURE['snapshot']['label']

    def test_multiple_injections_accumulate(self):
        result = inject_into_disclosure(EXISTING_DISCLOSURE, ROUND_AI_VALIDATOR)
        result = inject_into_disclosure(result, ROUND_DEMO_RUNNER)
        assert len(result['snapshot']['processing']['source']) == 2


# --- minimal_disclosure ---

class TestMinimalDisclosure:
    def test_top_level_keys(self):
        d = minimal_disclosure('example.com', ROUND_AI_VALIDATOR)
        assert {'schema', 'snapshot'} <= d.keys()

    def test_product_url(self):
        d = minimal_disclosure('https://loopchii.com/priorauth', ROUND_AI_VALIDATOR)
        assert d['snapshot']['product']['url'] == 'https://loopchii.com/priorauth'

    def test_generator_alias(self):
        d = minimal_disclosure('example.com', ROUND_AI_VALIDATOR)
        assert d['snapshot']['generator']['alias'] == 'valichord'

    def test_generator_type_is_third_party(self):
        d = minimal_disclosure('example.com', ROUND_AI_VALIDATOR)
        assert d['snapshot']['generator']['type'] == 'third-party'

    def test_source_entry_present(self):
        d = minimal_disclosure('example.com', ROUND_AI_VALIDATOR)
        sources = d['snapshot']['processing']['source']
        assert len(sources) == 1
        assert sources[0]['url'] == ROUND_AI_VALIDATOR['record_url']

    def test_label_required_fields(self):
        d = minimal_disclosure('example.com', ROUND_AI_VALIDATOR)
        label = d['snapshot']['label']
        assert {'data', 'source', 'decision'} <= label.keys()

    def test_timestamp_is_int_and_recent(self):
        before = int(time.time())
        d = minimal_disclosure('example.com', ROUND_AI_VALIDATOR)
        assert isinstance(d['snapshot']['timestamp'], int)
        assert d['snapshot']['timestamp'] >= before

    def test_schema_name(self):
        d = minimal_disclosure('example.com', ROUND_AI_VALIDATOR)
        assert d['schema']['name'] == 'Open Ethics Transparency Protocol'

    def test_does_not_mutate_round_result(self):
        original = copy.deepcopy(ROUND_AI_VALIDATOR)
        minimal_disclosure('example.com', ROUND_AI_VALIDATOR)
        assert ROUND_AI_VALIDATOR == original
