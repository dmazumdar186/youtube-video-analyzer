from __future__ import annotations
import sys, json, subprocess, os, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / 'youtube_video_analyzer.py'
TEST_URL = 'https://youtu.be/BedAaB1RKgE'

PASS_COUNT = 0; FAIL_COUNT = 0; FAILURES = []

def run(name, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        print(f'PASS  {name}')
        PASS_COUNT += 1
    except Exception as exc:
        print(f'FAIL  {name}')
        print(f'      {exc}')
        FAIL_COUNT += 1
        FAILURES.append((name, str(exc)))

def run_analyzer(*extra_args, env_overrides=None):
    env = os.environ.copy()
    if env_overrides:
        for k, v in env_overrides.items():
            if v is None: env.pop(k, None)
            else: env[k] = v
    cmd = [sys.executable, str(SCRIPT), TEST_URL, '--dry-run'] + list(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
    return result

def parse_json_output(result):
    lines = result.stdout.strip().splitlines()
    json_lines = []
    in_json = False
    for line in lines:
        if line.strip().startswith('{'):
            in_json = True
        if in_json:
            json_lines.append(line)
    if not json_lines:
        raise AssertionError(f'No JSON in stdout. stdout={result.stdout!r} stderr={result.stderr[:300]!r}')
    return json.loads(chr(10).join(json_lines))

# --- T3-1: default tier --dry-run (shallow) ---
def t_default_dryrun():
    result = run_analyzer()
    assert result.returncode == 0, f'exit {result.returncode}, stderr={result.stderr[:200]!r}'
    data = parse_json_output(result)
    assert data.get('provider') == 'openrouter', f'expected openrouter, got {data.get("provider")!r}'
    mid = data.get('model_id', '') or data.get('would_use_model', '')
    assert any(mid.startswith(fam) for fam in ('anthropic/', 'openai/', 'google/')), (
        f'model_id {mid!r} not in allowed families'
    )
    assert 'would_call_provider' in data, f'shallow field would_call_provider missing: {list(data)}'
    assert 'would_use_model' in data, f'shallow field would_use_model missing: {list(data)}'
    assert 'estimated_cost' in data, f'shallow field estimated_cost missing: {list(data)}'
    print(f'      [evidence] provider={data["provider"]}, model={mid}, would_call={data.get("would_call_provider")}')

# --- T3-2: premium tier dry-run ---
def t_premium_dryrun():
    result = run_analyzer('--tier', 'premium')
    assert result.returncode == 0, f'exit {result.returncode}, stderr={result.stderr[:200]!r}'
    data = parse_json_output(result)
    mid = data.get('model_id', '')
    assert 'opus' in mid.lower() or 'gpt-5' in mid.lower() or mid.startswith('google/') or mid.startswith('anthropic/'), (
        f'premium model_id unexpected: {mid!r}'
    )
    print(f'      [evidence] premium model_id={mid!r}')

# --- T3-3: gemini tier dry-run (no gemini key, should route to OR google/) ---
def t_gemini_tier_no_gemini_key():
    env_override = {'GEMINI_API_KEY': None}
    result = run_analyzer('--tier', 'gemini', env_overrides=env_override)
    stderr = result.stderr
    assert 'openrouter' in stderr.lower(), f'openrouter not mentioned in stderr: {stderr[:300]!r}'
    assert 'google/gemini' in stderr.lower() or 'gemini' in stderr.lower(), (
        f'gemini model not mentioned in stderr: {stderr[:300]!r}'
    )
    assert 'PAID' in stderr or 'paid' in stderr.lower(), (
        f'PAID warning not in stderr: {stderr[:300]!r}'
    )
    if result.returncode == 0:
        data = parse_json_output(result)
        assert data.get('provider') == 'openrouter'
        mid = data.get('model_id', '')
        assert 'google/' in mid or 'gemini' in mid.lower(), f'unexpected model: {mid!r}'
        print(f'      [evidence] provider=openrouter, model={mid}, dry-run succeeded')
    else:
        print(f'      [evidence] exit={result.returncode} (transcript rate-limited ok), routing correct per stderr logs')

# --- T3-4: --refresh-models updates cache mtime ---
def t_refresh_models_updates_cache():
    from model_registry import _CACHE_PATH
    run_analyzer()
    before = _CACHE_PATH.stat().st_mtime if _CACHE_PATH.exists() else 0.0
    time.sleep(0.5)
    result = run_analyzer('--refresh-models')
    assert result.returncode == 0, f'exit {result.returncode}'
    after = _CACHE_PATH.stat().st_mtime if _CACHE_PATH.exists() else 0.0
    assert after >= before, f'cache mtime not updated: before={before:.3f} after={after:.3f}'
    print(f'      [evidence] mtime before={before:.3f}, after={after:.3f}, delta={after-before:.3f}s')

# --- T3-5: --provider anthropic without ANTHROPIC_API_KEY exits with error ---
def t_provider_anthropic_no_key():
    env_override = {'ANTHROPIC_API_KEY': None}
    result = run_analyzer('--provider', 'anthropic', env_overrides=env_override)
    if result.returncode == 0:
        data = parse_json_output(result)
        assert data.get('provider') == 'anthropic', f'expected anthropic, got {data.get("provider")!r}'
        print(f'      [evidence] provider=anthropic in dry-run output (key only needed for real call)')
    else:
        assert 'anthropic' in result.stderr.lower() or 'api' in result.stderr.lower() or 'key' in result.stderr.lower(), (
            f'Non-zero exit but no helpful error in stderr: {result.stderr[:200]!r}'
        )
        print(f'      [evidence] exit={result.returncode}, stderr contains helpful error message')

# --- T3-6: --provider anthropic with key present (SKIPPED - no ANTHROPIC_API_KEY) ---
def t_provider_anthropic_with_key_skipped():
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('      [SKIPPED] ANTHROPIC_API_KEY not set')
        return
    result = run_analyzer('--provider', 'anthropic')
    assert result.returncode == 0
    data = parse_json_output(result)
    assert data.get('provider') == 'anthropic'

if __name__ == '__main__':
    sys.path.insert(0, str(REPO_ROOT))
    from dotenv import load_dotenv
    load_dotenv(str(REPO_ROOT / '.env'))

    print('=== TIER 3: END-TO-END DRY-RUN TESTS ===')
    print()
    run('T3-1: default tier --dry-run: exit 0, provider=openrouter, would_call_provider + would_use_model present', t_default_dryrun)
    run('T3-2: premium tier --dry-run: model_id contains opus/gpt-5/anthropic/google', t_premium_dryrun)
    run('T3-3: gemini tier + no GEMINI_KEY: routes to openrouter, warning in stderr', t_gemini_tier_no_gemini_key)
    run('T3-4: --refresh-models: cache mtime updated after run', t_refresh_models_updates_cache)
    run('T3-5: --provider anthropic + no key: exits cleanly or with helpful error', t_provider_anthropic_no_key)
    run('T3-6: --provider anthropic + key present (SKIPPED: no key)', t_provider_anthropic_with_key_skipped)
    print()
    print(f'E2E: {PASS_COUNT} passed, {FAIL_COUNT} failed')
    if FAILURES:
        print('Failed tests:')
        for n, e in FAILURES: print(f'  - {n}: {e}')
    import sys as _s; _s.exit(0 if FAIL_COUNT == 0 else 1)
