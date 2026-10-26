# RampTalk JP

Ear training for the spoken ramp words used at Japanese airports. A phone browser app for foreign ground-handling staff and the trainers at small regional stations.

- **Run it:** open `index.html` in a browser that has a Japanese voice. No install, no login, no server. "Say it" needs Chrome and a microphone.
- **One-minute path:** tap Play → choose a meaning → open *Ramp calls* → open *Supervisor* → "Load demo cohort (synthetic)".

## What is in this repo
| Path | What it is |
|---|---|
| `index.html` | The whole app (HTML, CSS, JavaScript; Web Speech API, Web Audio API, localStorage) |
| `proof/e2e_test.js`, `proof/test_report.txt` | Playwright end-to-end test, 20 of 20 checks |
| `proof/audio_check.py`, `proof/audio_check_report.txt` | Voice → offline recogniser (whisper.cpp) → the app's matching rule, per word |
| `proof/noise_sweep.py`, `proof/noise_sweep_report.txt` | Same check at four brown-noise levels, with measured SNR |

## Limits
The audio checks use a machine listener and one synthetic voice, not people. No test with ground-handling staff yet. The English meanings and the eight sample calls are mine and need an operator's check. The three learners in the demo cohort are synthetic.

## Sources
- MLIT Civil Aviation Bureau, survey report on accepting Specified Skilled Workers in airport ground handling (digest), Oct 2024. https://www.mlit.go.jp/koku/content/001846768.pdf
- MLIT, employer manual for Specified Skilled Workers in aviation (airport ground handling); starter glossary from p. 22. https://www.mlit.go.jp/koku/content/001846771.pdf
- Immigration Services Agency of Japan, Specified Skilled Worker: aviation. https://www.moj.go.jp/isa/policies/ssw/aviation.html

Built by Kotaro Kurosaki with an AI coding assistant (Claude Code).
