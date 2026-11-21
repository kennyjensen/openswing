# Capturing a new SA1 reference run

[`capture-isae-sa1-reference.py`](../../scripts/capture-isae-sa1-reference.py) prepares the unchanged, pinned SA1 model, driver and archived table. Preparation is the default and requires no executable:

```sh
.venv/bin/python scripts/capture-isae-sa1-reference.py \
  --prepare-only --output /tmp/sa1-capture-kit
```

The new directory contains `original/`, `original-run/`, an input/hash manifest and a portable copy of the script. `original-run/stdin.txt` is the exact original heredoc, including all 11 angle tokens, blank lines and trailing spaces. The shell driver is never executed. The archived table stays in `original/`, so it cannot be mistaken for newly produced output. Existing output directories are refused.

On a machine with an ASWING executable, explicitly supply its path and a **new** output directory:

```sh
python3 /tmp/sa1-capture-kit/capture-isae-sa1-reference.py \
  --input-kit /tmp/sa1-capture-kit \
  --output /tmp/sa1-new-reference-capture \
  --aswing /absolute/path/to/aswing --timeout 180
```

Only `--aswing` enables execution. The process receives the original `SA_1` argument and exact command bytes, without a shell or appended commands. Execution requires POSIX process groups; preparation is portable. A timeout, SIGTERM or SIGINT terminates the owned process group and reaps the direct process, escalating to SIGKILL after `--kill-grace` if needed. Temporary signal handlers are installed before process creation and restored after the terminal receipt is written. Cancellation during creation waits for the child handle so cleanup can still reach it. The inherited environment may require local display/runtime configuration; failures are retained rather than repaired.

Add `--settings-probe` to request a separate initial process containing only the documented main-menu commands `DIMS`, `SSAV`, its explicit filename, and `QUIT`. The probe receives its own copy of the original model and writes `settings-probe/SA_1_capture_startup.set`. The original run then starts independently in `original-run/`, without `.set`, `.pnt` or `.con` companions. Probe files never seed that run. The [guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt) documents these commands and automatic companion loading. A probe failure is retained; the independent original run can still proceed unless the executable changed or the capture was interrupted.

`capture.json` records actual UTC times, executable hashes before and after each launch, return codes, timeouts, direct-process reaping, input integrity and output hashes. SIGTERM/SIGINT produce terminal status `interrupted`, record the signal, prevent later stages from launching, and return 143/130 respectively. Each stage retains raw `stdout.log` and `stderr.log`. The new polar, if produced, is `original-run/SA_1_CL.txt`; partial output survives failures. Printed dates and native output bytes are not rewritten. `captured` means the requested file was retained after a zero exit with unchanged inputs; it does **not** mean the file is a valid polar or matches the archive. No automatic numerical comparison is made.

This packet records a new run of a supplied executable. It cannot recover the original ASWING 5.96 executable, startup settings, Fourier count or historical mesh. The tool performs no network requests. Focused tests use explicitly labelled fake executables to check capture mechanics, never as ASWING validation.
