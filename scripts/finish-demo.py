"""Export the real recording and public benchmark artifacts; never edits counts."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work' / 'demo'
OUT = ROOT / 'docs' / 'media'
OUT.mkdir(exist_ok=True)
recording = WORK / 'recording'
benchmark = json.loads((WORK / 'benchmark.json').read_text(encoding='utf-8'))
events = json.loads((recording / 'events.json').read_text(encoding='utf-8'))
milestones = {event['name']:event['seconds'] for event in events}
measured = benchmark['metrics']
recorded = next(event['metrics'] for event in events if event['name']=='run-finished')
if not benchmark['source_unchanged'] or measured['tracked'] != 50 or not measured['finished_at']:
    raise SystemExit('Need a complete 50-reel run with an unchanged source library.')
if recorded != measured:
    raise SystemExit('Recording and benchmark belong to different measurements.')
raw = recording / 'reelbox-raw.webm'
probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(raw)]))
duration = float(probe['format']['duration'])
if duration > 45:
    # Remove only pre/post-roll, never speed up the tracked transition.
    duration = min(duration, milestones['end'] + .3)
if not 30 <= duration <= 45:
    raise SystemExit(f'Recording is {duration:.1f}s; select honest cuts before exporting.')
font = 'C\\:/Windows/Fonts/segoeui.ttf'
details = benchmark['resolved_vision_model']
label = f"1x real time  |  Warm local alias - {details['family']} / {details['parameter_size']} / {details['quantization_level']}"
overlay = f"drawtext=fontfile='{font}':text='{label}':fontcolor=white:fontsize=12:x=w-tw-24:y=42:box=1:boxcolor=0x204b38@0.94:boxborderw=7"
# Normalize the first step caption in exports, including older Windows-console
# captures where the original em dash was encoded as a question mark.
step_start = milestones['entry'] + 4
step_end = milestones['processing-visible']
enabled = f"between(t,{step_start},{step_end})"
overlay += f",drawbox=x=192:y=653:w=1024:h=50:color=0x14251f:t=fill:enable='{enabled}'"
overlay += f",drawtext=fontfile='{font}':text='Step 1 - Follow one idea through the pipeline':fontcolor=white:fontsize=17:x=192+(1024-tw)/2:y=667:enable='{enabled}'"
subprocess.run(['ffmpeg','-v','error','-y','-i',str(raw),'-t',str(duration),'-vf',overlay,'-c:v','libx264','-preset','slow','-crf','24','-pix_fmt','yuv420p','-movflags','+faststart','-an',str(OUT/'reelbox-demo.mp4')],check=True)
start = max(0, milestones['resume'] - 2.5)
subprocess.run(['ffmpeg','-v','error','-y','-ss',str(start),'-t','10','-i',str(OUT/'reelbox-demo.mp4'),'-filter_complex','fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4','-loop','0',str(OUT/'reelbox-preview.gif')],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-ss',str(milestones['results']+.5),'-i',str(OUT/'reelbox-demo.mp4'),'-frames:v','1',str(OUT/'reelbox-demo-poster.jpg')],check=True)
(OUT/'benchmark.json').write_text(json.dumps(benchmark,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'Exported {duration:.1f}s MP4, 10s GIF and benchmark summary to {OUT}')
