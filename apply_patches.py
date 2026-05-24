#!/usr/bin/env python3
"""
Applies hardening patches to a cloned facefusion source tree.
Run from inside the facefusion clone directory:
    python3.11 ../apply_patches.py   # Massed Compute
    python ../apply_patches.py       # RunPod
"""
import pathlib
import sys


def apply(path: str, already_patched_marker: str, old: str, new: str, label: str) -> None:
	p = pathlib.Path(path)
	if not p.exists():
		print(f'SKIP  {label}: {path} not found (upstream structure may have changed)')
		return
	text = p.read_text()
	if already_patched_marker in text:
		print(f'SKIP  {label}: already patched')
		return
	if old not in text:
		print(f'WARN  {label}: anchor not found — upstream may have changed, skipping')
		return
	p.write_text(text.replace(old, new, 1))
	print(f'OK    {label}')


# ── Shared Python 3.11 gate block ────────────────────────────────────────────

PYTHON_GATE = (
	'import sys\n'
	'\n'
	'if sys.version_info < (3, 11):\n'
	'\tsys.exit(\n'
	'\t\t\'\\nERROR: FaceFusion requires Python 3.11 or higher.\\n\'\n'
	'\t\t\'You are using Python {}.{}.\\n\'\n'
	'\t\t\'Fix: deactivate your venv, then recreate it with:\\n\'\n'
	'\t\t\'  python3.11 -m venv venv && source venv/bin/activate\\n\'.format(\n'
	'\t\t\tsys.version_info.major, sys.version_info.minor\n'
	'\t\t)\n'
	'\t)\n'
	'\n'
)

# ── 1. install.py: Python 3.11 gate ──────────────────────────────────────────

apply(
	path='install.py',
	already_patched_marker='version_info < (3, 11)',
	old='#!/usr/bin/env python3\n\nimport os\n',
	new='#!/usr/bin/env python3\n\n' + PYTHON_GATE + 'import os\n',
	label='install.py: Python 3.11 gate',
)

# ── 2. facefusion.py: Python 3.11 gate + ORT log suppression ─────────────────

apply(
	path='facefusion.py',
	already_patched_marker='version_info < (3, 11)',
	old=(
		"#!/usr/bin/env python3\n"
		"\n"
		"import os\n"
		"\n"
		"os.environ['OMP_NUM_THREADS'] = '1'\n"
	),
	new=(
		'#!/usr/bin/env python3\n'
		'\n'
		+ PYTHON_GATE
		+ "import os\n"
		"\n"
		"os.environ['OMP_NUM_THREADS'] = '1'\n"
		"os.environ['ORT_LOGGING_LEVEL'] = '3'  # suppress onnxruntime device-discovery noise in containers\n"
	),
	label='facefusion.py: Python 3.11 gate + ORT log suppression',
)

# ── 3. facefusion/core.py: bump version floor, add CUDA check ────────────────

CORE_PATH = pathlib.Path('facefusion/core.py')
if not CORE_PATH.exists():
	print('SKIP  facefusion/core.py: file not found')
else:
	text = CORE_PATH.read_text()
	changed = False

	# 3a. Add re and subprocess imports
	OLD_IMPORTS = 'import inspect\nimport itertools\nimport shutil\n'
	NEW_IMPORTS = 'import inspect\nimport itertools\nimport re\nimport shutil\nimport subprocess\n'
	if 'import subprocess' not in text:
		if OLD_IMPORTS in text:
			text = text.replace(OLD_IMPORTS, NEW_IMPORTS, 1)
			changed = True
			print('OK    facefusion/core.py: added re/subprocess imports')
		else:
			print('WARN  facefusion/core.py: import anchor not found — skipping import patch')
	else:
		print('SKIP  facefusion/core.py: imports already patched')

	# 3b. Replace pre_check version floor + inject _check_cuda_version definition + call
	OLD_PRECHECK = (
		"\n"
		"\ndef pre_check() -> bool:\n"
		"\tif sys.version_info < (3, 10):\n"
		"\t\tlogger.error(translator.get('python_not_supported').format(version = '3.10'), __name__)\n"
		"\t\treturn False\n"
		"\n"
		"\tif not shutil.which('curl'):"
	)
	NEW_PRECHECK = (
		"\n"
		"\ndef _check_cuda_version() -> None:\n"
		"\ttry:\n"
		"\t\toutput = subprocess.check_output([ 'nvcc', '--version' ], stderr = subprocess.STDOUT, text = True)\n"
		"\t\tmatch = re.search(r'release (\\d+)\\.(\\d+)', output)\n"
		"\t\tif match:\n"
		"\t\t\tmajor = int(match.group(1))\n"
		"\t\t\tif major >= 13:\n"
		"\t\t\t\tsys.stderr.write(\n"
		"\t\t\t\t\t'[FACEFUSION.CORE] WARNING: detected CUDA ' + match.group(1) + '.' + match.group(2)\n"
		"\t\t\t\t\t+ '. onnxruntime-gpu supports CUDA 11.x and 12.x only.'\n"
		"\t\t\t\t\t+ ' GPU acceleration may not work.'\n"
		"\t\t\t\t\t+ ' Consider --execution-providers cpu or installing CUDA 12.x.\\n'\n"
		"\t\t\t\t)\n"
		"\texcept (FileNotFoundError, subprocess.CalledProcessError):\n"
		"\t\tpass\n"
		"\n"
		"\n"
		"def pre_check() -> bool:\n"
		"\tif sys.version_info < (3, 11):\n"
		"\t\tlogger.error(translator.get('python_not_supported').format(version = '3.11'), __name__)\n"
		"\t\treturn False\n"
		"\n"
		"\t_check_cuda_version()\n"
		"\n"
		"\tif not shutil.which('curl'):"
	)
	if '_check_cuda_version' not in text:
		if OLD_PRECHECK in text:
			text = text.replace(OLD_PRECHECK, NEW_PRECHECK, 1)
			changed = True
			print('OK    facefusion/core.py: bumped Python floor to 3.11 + CUDA version check')
		else:
			print('WARN  facefusion/core.py: pre_check anchor not found — upstream may have changed')
	else:
		print('SKIP  facefusion/core.py: CUDA/version patch already applied')

	if changed:
		CORE_PATH.write_text(text)

# ── 4. facefusion/processors/core.py: surface ModuleNotFoundError ────────────

apply(
	path='facefusion/processors/core.py',
	already_patched_marker="'hint: run `python install.py",
	old=(
		"\texcept ModuleNotFoundError as exception:\n"
		"\t\tlogger.error(translator.get('processor_not_loaded').format(processor = processor), __name__)\n"
		"\t\tlogger.debug(exception.msg, __name__)\n"
		"\t\thard_exit(1)"
	),
	new=(
		"\texcept ModuleNotFoundError as exception:\n"
		"\t\tlogger.error(translator.get('processor_not_loaded').format(processor = processor) + ': ' + str(exception), __name__)\n"
		"\t\tlogger.info('hint: run `python install.py --onnxruntime <default|cuda|...>` to install missing dependencies', __name__)\n"
		"\t\thard_exit(1)"
	),
	label='processors/core.py: surface ModuleNotFoundError with hint',
)

print('\nAll patches applied.')
