"""Audio round-trip check for RampTalk JP.

For each starter word and sample call: the macOS Japanese voice (Kyoko, the ja-JP voice Chrome uses on a Mac)
speaks the same text the app speaks, an offline speech recogniser (whisper.cpp, large-v3-turbo) transcribes it,
and the app's own matching rule decides whether the word was recovered. Run clean and with brown noise mixed in.
This checks that the synthetic voice says the clipped loanwords clearly enough for a machine to recover them.
It is not a test with human listeners.
"""
import json, re, subprocess, sys, os, tempfile, datetime

HTML, OUT = sys.argv[1], sys.argv[2]
MODEL = os.path.expanduser('~/.local/share/whisper/ggml-large-v3-turbo-q5_0.bin')
src = open(HTML, encoding='utf-8').read()
words = re.findall(r'\{id:"(\w+)",\s*term:"([^"]+)",\s*read:"([^"]+)"', src)
calls = re.findall(r'\{say:"([^"]+)", text:"([^"]+)"', src)
CALL_KEYS = ['アンコリ', 'アンコリ', 'ドアサイド', 'コネクションバゲージ', 'ビーピー', 'リメイン', 'スポット', 'ショーアップ']

def to_hira(s): return ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in s)
def norm(s): return re.sub(r'[\s・、。,.\-()（）/A-Za-z!?！？「」]', '', to_hira(s or ''))
def abbr(term):
    m = re.search(r'\(([^)]+)\)', term); return re.sub(r'[^A-Za-z]', '', m.group(1)).upper() if m else ''
def hit(target, heard, ab=''):  # same rule as the app's "Say it" check
    t, n = norm(target), norm(heard)
    return bool(t in n or (n in t and len(n) >= 2) or (ab and ab in re.sub(r'[^A-Z]', '', heard.upper())))

tmp = tempfile.mkdtemp()
def transcribe(text, noise):
    aiff, wav = os.path.join(tmp, 'a.aiff'), os.path.join(tmp, 'a.wav')
    subprocess.run(['say', '-v', 'Kyoko', '-o', aiff, text], check=True)
    if noise:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', aiff, '-f', 'lavfi', '-i', 'anoisesrc=color=brown:amplitude=0.25',
                        '-filter_complex', '[0:a]aresample=16000,apad=pad_dur=0.3[v];[1:a]aresample=16000[n];[v][n]amix=inputs=2:duration=first:normalize=0',
                        '-ac', '1', '-ar', '16000', wav], check=True)
    else:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', aiff, '-ac', '1', '-ar', '16000', wav], check=True)
    r = subprocess.run(['whisper-cli', '-m', MODEL, '-l', 'ja', '-nt', '-np', '-f', wav], capture_output=True, text=True)
    return r.stdout.strip().replace('\n', ' ')

rows, summary = [], {}
for cond, kana, noise in (('v1 hiragana, clean', False, False), ('v2 katakana, clean', True, False), ('v2 katakana, noise', True, True)):
    ok_w = 0
    for wid, term, read in words:
        katakana = re.sub(r'\s*\(.*\)', '', term)
        heard = transcribe(katakana if kana else read, noise)
        ok = hit(read, heard, abbr(term))
        ok_w += ok; rows.append((cond, 'word', term, heard, ok))
    ok_c = 0
    for (say, text), key in zip(calls, CALL_KEYS):
        heard = transcribe(say, noise)
        ok = hit(key, heard, 'BP' if key == 'ビーピー' else '')
        ok_c += ok; rows.append((cond, 'call', text + '  [key: ' + key + ']', heard, ok))
    summary[cond] = (ok_w, len(words), ok_c, len(calls))

lines = ['RampTalk JP audio round-trip check',
         f'Run: {datetime.datetime.now().isoformat(timespec="seconds")}  Voice: macOS Kyoko (ja-JP)  Recogniser: whisper.cpp large-v3-turbo (offline)',
         'Method: speak the text the app speaks (v1 spoke the hiragana reading; v2, the current version, speaks the katakana term) -> transcribe -> apply the app\'s own matching rule. Noise: brown noise, amplitude 0.25, mixed at equal gain.',
         'Limits: a machine listener, not people; one synthetic voice; says nothing about learners\' own pronunciation.', '']
for cond, (w, wn, c, cn) in summary.items():
    lines.append(f'{cond}: words recovered {w}/{wn}, key word recovered in calls {c}/{cn}')
lines.append('')
for cond, kind, item, heard, ok in rows:
    lines.append(f'[{"OK" if ok else "MISS"}] {cond:20} {kind:4} {item}  ->  heard: {heard}')
open(OUT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('\n'.join(lines[:8]))
