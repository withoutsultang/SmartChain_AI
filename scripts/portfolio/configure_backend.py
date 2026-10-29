"""Isolated PostgreSQL/local-files config, preserving production slot definitions."""
from pathlib import Path
import yaml
source = Path('backend/src/main/resources/application.yaml').read_text()
base = yaml.safe_load(source.split('---')[0])
config = yaml.safe_load(source.split('---')[1])
config['spring']['servlet'] = base['spring']['servlet']
config['spring'].pop('profiles', None)
config['spring'].pop('config', None)
config['spring']['profiles'] = {'active': 'local'}
config['spring']['datasource'].update(url='jdbc:postgresql://localhost:5432/smartchain', username='esg', password='portfolio-local-only')
config['spring']['jpa']['show-sql'] = False
config['spring']['mail'] = {'host': 'localhost', 'port': 1025}
config['server'] = {'port': 8080, 'address': '127.0.0.1'}
config['logging'] = {'level': {'root': 'WARN', 'com.smartchain.platform': 'INFO'}}
config['ai']['run-api'].update({'timeout-seconds': 180, 'max-retry': 0})
config['file']['storage']['local']['base-path'] = str(Path('backend/uploads').resolve())
config['jwt']['secret'] = 'portfolioIsolatedValidationSecretAtLeast256BitsLongNeverProduction'
Path('/tmp/portfolio-backend.yaml').write_text(yaml.safe_dump(config, allow_unicode=True))
