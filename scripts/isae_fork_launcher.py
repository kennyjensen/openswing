"""Fresh serial worker processes inheriting imports from a single-threaded parent.

The parent never runs an adapter or constructs a solver state. The existing
suite supervisor still owns deadlines, process-group termination, exit receipts,
artifact validation and all comparison decisions.
"""
import asyncio
import importlib.util
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import traceback


class ForkProcess:
    def __init__(self, pid):
        self.pid = pid
        self.returncode = None

    async def wait(self):
        while self.returncode is None:
            found, status = os.waitpid(self.pid, os.WNOHANG)
            if found:
                self.returncode = os.waitstatus_to_exitcode(status)
            else:
                await asyncio.sleep(.05)
        return self.returncode


def make_launcher(worker, runner_path):
    runner_path = str(Path(runner_path).resolve())

    async def launch(*command, cwd, env, stdout, stderr, start_new_session):
        if not hasattr(os, 'fork'):
            raise RuntimeError('This launcher requires POSIX fork')
        if (len(command) != 5 or command[0] != sys.executable or
                str(Path(command[1]).resolve()) != runner_path or command[2] != '--worker' or
                start_new_session is not True):
            raise ValueError('Unexpected worker command')
        if len(os.listdir('/proc/self/task')) != 1:
            raise RuntimeError('Refuse to fork a multithreaded parent')
        if any(env.get(key) != '1' for key in
               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')):
            raise ValueError('Each worker must retain one BLAS thread')
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        if pid == 0:
            try:
                os.setsid()
                os.chdir(cwd)
                os.environ.clear()
                os.environ.update(env)
                # The parent may already have resolved a temporary directory.
                # Each child must honor the original per-job artifact directory.
                tempfile.tempdir = None
                os.dup2(stdout.fileno(), 1)
                os.dup2(stderr.fileno(), 2)
                sys.argv = list(command[1:])
                worker(command[3], command[4])
                sys.stdout.flush()
                sys.stderr.flush()
            except SystemExit as exc:
                code = exc.code
                if code is None:
                    code = 0
                elif not isinstance(code, int):
                    print(code, file=sys.stderr)
                    code = 1
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(code)
            except BaseException:
                traceback.print_exc()
                sys.stderr.flush()
                os._exit(1)
            os._exit(0)
        return ForkProcess(pid)

    return launch


class ServerProcess:
    def __init__(self, process):
        self.process = process
        self.pid = process.pid

    @property
    def returncode(self):
        return self.process.exitcode

    async def wait(self):
        while self.process.exitcode is None:
            await asyncio.sleep(.05)
        self.process.join()
        return self.process.exitcode


def server_worker(command, cwd, env, stdout_path, stderr_path):
    """Executed in a fresh child of the clean import server, without plan/results."""
    os.setsid()
    if len(os.listdir('/proc/self/task')) != 1:
        raise RuntimeError('Worker must start with one thread')
    os.chdir(cwd)
    os.environ.clear()
    os.environ.update(env)
    tempfile.tempdir = None
    for path, fd in ((stdout_path, 1), (stderr_path, 2)):
        opened = os.open(path, os.O_WRONLY | os.O_APPEND)
        os.dup2(opened, fd)
        os.close(opened)
    sys.argv = list(command[1:])
    spec = importlib.util.spec_from_file_location('isae_server_worker', command[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.worker(command[3], command[4])


def make_server_launcher(runner_path, preload_modules):
    """Reuse imports in a clean Python server; parent result size is irrelevant."""
    runner_path = str(Path(runner_path).resolve())
    context = multiprocessing.get_context('forkserver')
    context.set_forkserver_preload(list(preload_modules))

    async def launch(*command, cwd, env, stdout, stderr, start_new_session):
        if (len(command) != 5 or command[0] != sys.executable or
                str(Path(command[1]).resolve()) != runner_path or command[2] != '--worker' or
                start_new_session is not True):
            raise ValueError('Unexpected worker command')
        if any(env.get(key) != '1' or os.environ.get(key) != '1' for key in
               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')):
            raise ValueError('Parent and worker must retain one BLAS thread')
        process = context.Process(target=server_worker,
            args=(command, str(cwd), env, stdout.name, stderr.name))
        process.start()
        return ServerProcess(process)

    return launch
