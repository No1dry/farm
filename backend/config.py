"""Explicit server configuration; secrets stay in ignored runtime files/environment."""
import json
import os
from pathlib import Path
import secrets
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
ENV_KEYS={'FARM_DB_PATH':'db_path','FARM_MODEL_BASE_URL':'model_base_url','FARM_MODEL_NAME':'model_name',
          'FARM_MODEL_API_KEY':'model_api_key','FARM_MODEL_TIMEOUT_SECONDS':'model_timeout_seconds',
          'FARM_MODEL_MAX_TOKENS':'model_max_tokens','FARM_MODEL_CONSTRAINED_JSON':'model_constrained_json',
          'FARM_AUTH_MODE':'auth_mode','FARM_ADMIN_TOKEN':'admin_token','FARM_OPERATOR_TOKEN':'operator_token'}


def load_settings(root=ROOT):
    path=Path(os.environ.get('FARM_CONFIG_FILE',root/'runtime/backend-config.json'))
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        settings={'schema_version':1,'auth_mode':'local','admin_token':secrets.token_urlsafe(32),
            'operator_token':secrets.token_urlsafe(32),'session_secret':secrets.token_urlsafe(48),
            'model_base_url':'','model_name':'','model_api_key':'','model_timeout_seconds':90}
        path.write_text(json.dumps(settings,indent=2)+'\n',encoding='utf8')
    settings=json.loads(path.read_text(encoding='utf-8-sig'))
    env={**dotenv_values(root/'.env'),**os.environ}
    for key,target in ENV_KEYS.items():
        if key in env and env[key] is not None:
            settings[target]=env[key]
    settings.setdefault('db_path',str(root/'runtime/farm.sqlite3'))
    settings.setdefault('auth_mode','local')
    if settings['auth_mode'] not in ('local','token','readonly'):
        raise ValueError('FARM_AUTH_MODE must be local, token or readonly')
    settings['model_max_tokens']=int(settings.get('model_max_tokens',1800))
    value=settings.get('model_constrained_json',False)
    if isinstance(value,str):
        if value.lower() not in ('true','false'):raise ValueError('FARM_MODEL_CONSTRAINED_JSON must be true or false')
        value=value.lower()=='true'
    settings['model_constrained_json']=value
    if not Path(settings['db_path']).is_absolute():settings['db_path']=str(root/settings['db_path'])
    return settings
