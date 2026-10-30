"""Cross-repository contract check: actual engine definitions and deployed YAML flags."""
from pathlib import Path
import argparse
import json
import sys
import yaml

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'apps/ai_run_api'))
from app.engines.esg.slots import get_required_slot_names

parser = argparse.ArgumentParser()
parser.add_argument('--backend', type=Path, required=True)
args = parser.parse_args()
expected = set(json.loads((root / 'contracts/esg-required-slots.json').read_text())['required_slots'])
assert set(get_required_slot_names()) == expected, 'AI engine diverged from canonical ESG contract'

sources = [args.backend/'src/main/resources/application.yaml', args.backend/'src/test/resources/application-test.yaml']
for source in sources:
    found = 0
    for config in yaml.safe_load_all(source.read_text()):
        definitions = (config or {}).get('ai', {}).get('slots', {}).get('domains', {}).get('esg')
        if definitions:
            actual = {item['name'] for item in definitions if item.get('required')}
            assert actual == expected, f'{source.name}: missing={sorted(expected-actual)}, unexpected={sorted(actual-expected)}'
            found += 1
    assert found, f'No ESG slot configuration in {source}'
print(json.dumps({'domain':'esg','required_count':len(expected),'required_slots':sorted(expected),'backend_configs_verified':len(sources)}))
