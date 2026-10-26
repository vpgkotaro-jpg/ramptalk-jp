"""Noise-level sweep for RampTalk JP (adds to audio_check.py).

Same pipeline as audio_check.py (macOS Kyoko voice -> whisper.cpp -> the app's matching rule), v2 katakana only,
with brown noise at several amplitudes. For each level the speech-to-noise ratio (SNR) is measured from the two
signals before mixing, so the result can be read without knowing ffmpeg's amplitude scale.
A machine listener, not people.
"""
import re, subprocess, sys, os, tempfile, datetime, wave, array, math
sys.path.insert(0, os.path.dirname(__file__))
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
def hit(target, heard, ab=''):
    t, n = norm(target), norm(heard)
    return bool(t in n or (n in t and len(n) >= 2) or (ab and ab in re.sub(r'[^A-Z]', '', heard.upper())))
def rms(path):
    w = wave.open(path); a = array.array('h', w.readframes(w.getnframes())); w.close()
    return math.sqrt(sum(x * x for x in a) / max(1, len(a)))
tmp = tempfile.mkdtemp()
def run(cmd): subprocess.run(cmd, check=True)
def transcribe(text, amp):
    aiff, sp, nz, mix = [os.path.join(tmp, n) for n in ('a.aiff', 's.wav', 'n.wav', 'm.wav')]
    run(['say', '-v', 'Kyoko', '-o', aiff, text])
    run(['ffmpeg', '-y', '-v', 'error', '-i', aiff, '-af', 'aresample=16000,apad=pad_dur=0.3', '-ac', '1', '-ar', '16000', sp])
    snr = None
    if amp:
        w = wave.open(sp); dur = w.getnframes() / w.getframerate(); w.close()
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'anoisesrc=color=brown:amplitude={amp}:sample_rate=16000', '-t', str(dur), '-ac', '1', nz])
        run(['ffmpeg', '-y', '-v', 'error', '-i', sp, '-i', nz, '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:normalize=0', '-ac', '1', '-ar', '16000', mix])
        snr = 20 * math.log10(rms(sp) / max(1e-9, rms(nz)))
    r = subprocess.run(['whisper-cli', '-m', MODEL, '-l', 'ja', '-nt', '-np', '-f', mix if amp else sp], capture_output=True, text=True)
    return r.stdout.strip().replace('\n', ' '), snr
LEVELS = [0, 0.03, 0.06, 0.12, 0.25]
rows, summary = [], []
for amp in LEVELS:
    ok_w = ok_c = 0; snrs = []
    for wid, term, read in words:
        heard, snr = transcribe(re.sub(r'\s*\(.*\)', '', term), amp)
        ok = hit(read, heard, abbr(term)); ok_w += ok; snrs += [snr] if snr is not None else []
        rows.append((amp, 'word', term, heard, ok))
    for (say, text), key in zip(calls, CALL_KEYS):
        heard, snr = transcribe(say, amp)
        ok = hit(key, heard, 'BP' if key == 'ビーピー' else ''); ok_c += ok; snrs += [snr] if snr is not None else []
        rows.append((amp, 'call', text + '  [key: ' + key + ']', heard, ok))
    med = sorted(snrs)[len(snrs) // 2] if snrs else None
    summary.append((amp, med, ok_w, len(words), ok_c, len(calls)))
    print(amp, med, ok_w, ok_c, flush=True)
lines = ['RampTalk JP noise-level sweep (v2 katakana voice)',
         f'Run: {datetime.datetime.now().isoformat(timespec="seconds")}  Voice: macOS Kyoko (ja-JP)  Recogniser: whisper.cpp large-v3-turbo (offline)',
         'Method: as audio_check.py; brown noise at each amplitude mixed at equal gain; SNR = speech RMS / noise RMS before mixing (median over items).',
         'Limits: a machine listener, not people; one synthetic voice; brown noise is a stand-in for real apron noise, which was not recorded.', '',
         'amplitude | median SNR | words recovered | key word in calls']
for amp, med, w, wn, c, cn in summary:
    lines.append(f'{amp:<9} | {"clean" if med is None else f"{med:+.1f} dB":>10} | {w}/{wn} | {c}/{cn}')
lines.append('')
for amp, kind, item, heard, ok in rows:
    lines.append(f'[{"OK" if ok else "MISS"}] amp={amp:<5} {kind:4} {item}  ->  heard: {heard}')
open(OUT, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
