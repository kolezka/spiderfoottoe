from pathlib import Path

import yaml


def test_wiki_sync_skips_only_explicitly_disabled_wikis():
    workflow = Path(__file__).resolve().parents[2] / '.github/workflows/wiki-sync.yml'
    job = yaml.safe_load(workflow.read_text())['jobs']['sync-wiki']
    # JSON comparison distinguishes an absent field (null) from false.
    assert job.get('if') == "toJSON(github.event.repository.has_wiki) != 'false'"
