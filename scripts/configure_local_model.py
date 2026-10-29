"""Configure the downloaded local provider; never print authentication secrets."""
import json
from pathlib import Path
import secrets
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import load_settings,ROOT

load_settings()
path=Path(os.environ.get('FARM_CONFIG_FILE',ROOT/'runtime/backend-config.json'))
saved=json.loads(path.read_text(encoding='utf8'))
saved.update(model_base_url='http://127.0.0.1:8081/v1',model_name='qwen3-4b-local',
    model_api_key=saved.get('model_api_key') or secrets.token_urlsafe(40),model_timeout_seconds=120,model_max_tokens=1800,model_constrained_json=True)
path.write_text(json.dumps(saved,indent=2)+'\n',encoding='utf8')
(ROOT/'runtime/model-api-key.txt').write_text(saved['model_api_key']+'\n',encoding='utf8')
print('Local model configured. Credentials remain in ignored runtime files.')
