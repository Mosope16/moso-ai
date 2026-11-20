"""Offline regression tests for mandatory GitHub evidence gating."""
import unittest
from datetime import datetime, timezone

from backend.web.github import parse_github_target
from backend.web.evidence import EvidenceContract
from backend.verification.classifier import classify_query
from backend.verification.evidence_gating import EvidenceRegistry, evaluate_evidence_gating


def make_contract(*, owner='Mosope16', repo='moso-ai', identity=True, success=True):
    return EvidenceContract(
        success=success,
        tool='github_inspect',
        requested_url=f'https://github.com/{owner}/{repo}',
        resolved_url=f'https://github.com/{owner}/{repo}',
        http_status=200 if success else 503,
        content_type='text/markdown',
        title=f'GitHub: {owner}/{repo}',
        source_name=f'GitHub ({owner}/{repo})',
        retrieved_content='Repository README and source file evidence.' if success else '',
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        error=None if success else 'network unavailable',
        error_type=None if success else 'connection_failure',
        metadata={
            'owner': owner,
            'repo': repo,
            'identity_verified': identity,
            'readme_available': True,
            'files_retrieved': ['README.md'],
        },
    )


class GitHubGateRegressionTests(unittest.TestCase):
    def setUp(self):
        self.query = 'Please inspect https://github.com/Mosope16/moso-ai and explain it.'
        self.intent = classify_query(self.query)

    def test_github_url_is_detected_inside_prose(self):
        self.assertEqual(self.intent.task_type, 'github_inspect')
        self.assertEqual(self.intent.entities['github_target'][:2], ('Mosope16', 'moso-ai'))

    def test_url_with_sentence_punctuation_and_git_suffix(self):
        self.assertEqual(
            parse_github_target('https://github.com/Mosope16/moso-ai.git?'),
            ('Mosope16', 'moso-ai', None),
        )

    def test_no_retrieval_abstains(self):
        decision = evaluate_evidence_gating(self.intent, self.query, EvidenceRegistry())
        self.assertTrue(decision.requires_abstention)
        self.assertFalse(decision.can_proceed_to_model)

    def test_failed_retrieval_abstains(self):
        registry = EvidenceRegistry()
        registry.add_contract(make_contract(success=False))
        decision = evaluate_evidence_gating(self.intent, self.query, registry)
        self.assertTrue(decision.requires_abstention)

    def test_identity_unverified_is_not_groundable(self):
        contract = make_contract(identity=False)
        self.assertFalse(contract.is_groundable())
        registry = EvidenceRegistry()
        registry.add_contract(contract)
        decision = evaluate_evidence_gating(self.intent, self.query, registry)
        self.assertTrue(decision.requires_abstention)

    def test_different_repository_identity_abstains(self):
        registry = EvidenceRegistry()
        registry.add_contract(make_contract(owner='AnotherOwner', repo='moso-ai'))
        decision = evaluate_evidence_gating(self.intent, self.query, registry)
        self.assertTrue(decision.requires_abstention)

    def test_exact_identity_and_content_can_proceed(self):
        registry = EvidenceRegistry()
        registry.add_contract(make_contract())
        decision = evaluate_evidence_gating(self.intent, self.query, registry)
        self.assertFalse(decision.requires_abstention)
        self.assertTrue(decision.can_proceed_to_model)


if __name__ == '__main__':
    unittest.main(verbosity=2)
