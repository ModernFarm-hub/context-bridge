# SPDX-License-Identifier: Apache-2.0
"""Local credential filtering. No external service, logs, or telemetry."""
import re

REDACTION_VERSION = 3
MARKER = '[REDACTED]'
PRIVATE_KEY = re.compile(r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----[\s\S]*?(?:-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----|\Z)')
TOKENS = re.compile(r'(?<![\w-])(?:sk-(?:(?:ant|proj|svcacct)-)?[A-Za-z0-9_-]{8,}|(?:sk|rk)_(?:live|test)_[A-Za-z0-9_]{8,}|AIza[0-9A-Za-z_-]{35}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|xox[baprs]-[A-Za-z0-9-]{8,})(?![\w-])')
JWT = re.compile(r'(?<![\w-])eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?![\w.-])')
URL_PASSWORD = re.compile(r'(?P<prefix>\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]+:)(?P<password>[^\s/@]+)(?=@)')
BEARER = re.compile(r'(?i)\b(Bearer\s+)(?!\[REDACTED\])[^\s\"\'<>`,;]+')
KEY = r'(?:[A-Z][A-Z0-9_]*_(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS?|KEY_ID)|APIKEY|ACCESSKEY|SECRETKEY|CLIENTSECRET|ACCESSTOKEN|REFRESHTOKEN|AUTHTOKEN|KEY|TOKEN|SECRET|PASSWORD|PASSWD|DATABASE_URL)'
SCHEMA_KEY = r'(?:primary_key|foreign_key|sort_key|partition_key|unique_key|idempotency_key|cache_key|key_id)'
ENV = re.compile(r'''(?im)(\b(?!'''+SCHEMA_KEY+r'''\b)'''+KEY+r'''\s*=\s*)(?!\[REDACTED\])(?:"[^"\n]*"|'[^'\n]*'|[^\s#`;,]+)''')
CREDENTIAL_KEY = r'(?:api_key|access_key|secret_key|private_key|client_secret|auth_token|access_token|refresh_token|password|passwd|secret|token|credentials|apiKey|accessKey|secretKey|privateKey|clientSecret|authToken|accessToken|refreshToken)'
WEBHOOK = re.compile(r'https://(?:(?:hooks\.slack\.com/services/)|(?:(?:(?:canary|ptb)\.)?discord(?:app)?\.com/api(?:/v[0-9]+)?/webhooks/))[^\s\"\'<>`]+', re.I)
STRUCTURED = re.compile(r'''(?im)(?<![\w])(?P<prefix>(?:"'''+CREDENTIAL_KEY+r'''"|\x27'''+CREDENTIAL_KEY+r'''\x27|'''+CREDENTIAL_KEY+r''')\s*:\s*)(?!\[REDACTED\])(?P<value>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|[^\s,}\]#`]+)''')


def redact(value):
    if not isinstance(value, str):
        return value
    value = PRIVATE_KEY.sub(MARKER, value)
    value = WEBHOOK.sub(MARKER, value)
    value = URL_PASSWORD.sub(lambda m: m['prefix']+MARKER, value)
    value = ENV.sub(lambda m: m[1]+MARKER, value)
    def structured(match):
        raw = match['value']
        if raw in ('[REDACTED]', '"[REDACTED]"', "'[REDACTED]'", 'null', 'None', '~'):
            return match[0]
        # Preserve JSON/YAML quotes and benign syntax around the credential.
        replacement = raw[0]+MARKER+raw[-1] if raw[:1] in ('"', "'") else MARKER
        return match['prefix']+replacement
    value = STRUCTURED.sub(structured, value)
    value = TOKENS.sub(MARKER, value)
    value = JWT.sub(MARKER, value)
    return BEARER.sub(lambda m: m[1]+MARKER, value)
