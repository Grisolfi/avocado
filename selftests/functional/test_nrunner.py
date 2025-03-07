import os
import sys
import unittest

from avocado.core.job import Job
from avocado.utils import process
from selftests.utils import AVOCADO, BASEDIR, TestCaseTmpDir, skipUnlessPathExists

RUNNER = "avocado-runner-noop"


class NRunnerFeatures(TestCaseTmpDir):
    @skipUnlessPathExists("/bin/false")
    def test_custom_exit_codes(self):
        config = {
            "run.results_dir": self.tmpdir.name,
            "resolver.references": ["/bin/false"],
            "runner.exectest.exitcodes.skip": [1],
        }
        with Job.from_config(job_config=config) as job:
            self.assertEqual(job.run(), 0)

    @skipUnlessPathExists("/bin/false")
    @skipUnlessPathExists("/bin/true")
    def test_failfast(self):
        config = {
            "run.results_dir": self.tmpdir.name,
            "resolver.references": [
                "/bin/true",
                "/bin/false",
                "/bin/true",
                "/bin/true",
            ],
            "run.failfast": True,
            "run.shuffle": False,
            "run.max_parallel_tasks": 1,
        }
        with Job.from_config(job_config=config) as job:
            self.assertEqual(job.run(), 9)
            self.assertEqual(job.result.passed, 1)
            self.assertEqual(job.result.errors, 0)
            self.assertEqual(job.result.failed, 1)
            self.assertEqual(job.result.skipped, 2)


class RunnableRun(unittest.TestCase):
    def test_noop(self):
        res = process.run(f"{RUNNER} runnable-run -k noop", ignore_status=True)
        self.assertIn(b"'status': 'started'", res.stdout)
        self.assertIn(b"'status': 'finished'", res.stdout)
        self.assertIn(b"'time': ", res.stdout)
        self.assertEqual(res.exit_status, 0)

    def test_instrumented(self):
        test_uri = os.path.join(
            BASEDIR, "examples", "tests", "passtest.py:PassTest.test"
        )
        res = process.run(
            f"{RUNNER} runnable-run -k avocado-instrumented -u " f"{test_uri}",
            ignore_status=True,
        )
        self.assertIn(b"'status': 'started'", res.stdout)
        self.assertIn(b"'status': 'finished'", res.stdout)
        self.assertIn(b"'result': 'pass'", res.stdout)
        self.assertIn(b"'time': ", res.stdout)
        self.assertEqual(res.exit_status, 0)

    def test_exec_test(self):
        # 'base64:LWM=' becomes '-c' and makes Python execute the
        # commands on the subsequent argument
        cmd = (
            f"{RUNNER} runnable-run -k exec-test -u {sys.executable} "
            f"-a 'base64:LWM=' -a 'import sys; sys.exit(99)'"
        )
        res = process.run(cmd, ignore_status=True)
        self.assertIn(b"'status': 'finished'", res.stdout)
        self.assertIn(b"'returncode': 99", res.stdout)
        self.assertEqual(res.exit_status, 0)

    @skipUnlessPathExists("/bin/sh")
    def test_exec_test_echo(self):
        # 'base64:LW4=' becomes '-n' and prevents echo from printing a newline
        cmd = (
            f"{RUNNER} runnable-run -k exec-test -u /bin/echo "
            f"-a 'base64:LW4=' -a _Avocado_Runner_"
        )
        res = process.run(cmd, ignore_status=True)
        self.assertIn(b"'status': 'finished'", res.stdout)
        self.assertIn(b"'log': b'_Avocado_Runner_'", res.stdout)
        self.assertIn(b"'returncode': 0", res.stdout)
        self.assertEqual(res.exit_status, 0)

    @skipUnlessPathExists("/bin/sh")
    @skipUnlessPathExists("/bin/echo")
    def test_exec_recipe(self):
        recipe = os.path.join(
            BASEDIR,
            "examples",
            "nrunner",
            "recipes",
            "runnables",
            "exec_test_sh_echo_env_var.json",
        )
        cmd = f"{RUNNER} runnable-run-recipe {recipe}"
        res = process.run(cmd, ignore_status=True)
        lines = res.stdout_text.splitlines()
        if len(lines) == 1:
            first_status = final_status = lines[0]
        else:
            first_status = lines[0]
            stdout_status = lines[-3]
            final_status = lines[-1]
            self.assertIn("'status': 'started'", first_status)
            self.assertIn("'time': ", first_status)
        self.assertIn("'status': 'finished'", final_status)
        self.assertIn("'log': b'Hello world!\\n'", stdout_status)
        self.assertIn("'time': ", final_status)
        self.assertEqual(res.exit_status, 0)

    def test_noop_valid_kwargs(self):
        res = process.run(f"{RUNNER} runnable-run -k noop foo=bar", ignore_status=True)
        self.assertEqual(res.exit_status, 0)

    def test_noop_invalid_kwargs(self):
        res = process.run(f"{RUNNER} runnable-run -k noop foo", ignore_status=True)
        self.assertIn(b'Invalid keyword parameter: "foo"', res.stderr)
        self.assertEqual(res.exit_status, 2)

    @skipUnlessPathExists("/bin/env")
    def test_exec_test_kwargs(self):
        cmd = f"{RUNNER} runnable-run -k exec-test -u /bin/env X=Y"
        res = process.run(cmd, ignore_status=True)
        self.assertIn(b"'status': 'finished'", res.stdout)
        self.assertIn(b"X=Y\\n", res.stdout)
        self.assertEqual(res.exit_status, 0)


class ExecTestStdOutErr(unittest.TestCase):
    def test_64kib(self):
        path = os.path.join(
            BASEDIR, "selftests", ".data", "exec_test_std", "exec_test_64kib.py"
        )
        res = process.run(
            f"avocado-runner-exec-test runnable-run -u {path}", ignore_status=True
        )
        self.assertIn(b"'type': 'stdout'", res.stdout)
        self.assertIn(b"'type': 'stderr'", res.stdout)
        self.assertIn(b"'result': 'pass'", res.stdout)
        self.assertIn(b"'returncode': 0", res.stdout)
        self.assertEqual(res.exit_status, 0)


class ExecTestStdOutErrOutputDir(TestCaseTmpDir):
    def test_1mib(self):
        path = os.path.join(
            BASEDIR, "selftests", ".data", "exec_test_std", "exec_test_1mib.py"
        )
        res = process.run(
            f"avocado-runner-exec-test runnable-run -u {path} output_dir={self.tmpdir.name}",
            ignore_status=True,
        )
        self.assertIn(b"'type': 'stdout'", res.stdout)
        self.assertIn(b"'type': 'stderr'", res.stdout)
        self.assertIn(b"'result': 'pass'", res.stdout)
        self.assertIn(b"'returncode': 0", res.stdout)
        self.assertEqual(res.exit_status, 0)

    def test_error_existing_stdout_stderr(self):
        self.test_1mib()
        path = os.path.join(
            BASEDIR, "selftests", ".data", "exec_test_std", "exec_test_1mib.py"
        )
        res = process.run(
            f"avocado-runner-exec-test runnable-run -u {path} output_dir={self.tmpdir.name}",
            ignore_status=True,
        )
        self.assertIn(b"'result': 'error'", res.stdout)
        self.assertEqual(res.exit_status, 0)


class TaskRun(unittest.TestCase):
    def test_noop(self):
        res = process.run(
            f"{RUNNER} task-run -i XXXno-opXXX -k noop", ignore_status=True
        )
        self.assertIn(b"'status': 'finished'", res.stdout)
        self.assertIn(b"'id': 'XXXno-opXXX'", res.stdout)
        self.assertEqual(res.exit_status, 0)

    @skipUnlessPathExists("/bin/uname")
    def test_recipe_exec_test_1(self):
        recipe = os.path.join(
            BASEDIR,
            "examples",
            "nrunner",
            "recipes",
            "tasks",
            "exec-test",
            "1-uname.json",
        )
        cmd = f"{RUNNER} task-run-recipe {recipe}"
        res = process.run(cmd, ignore_status=True)
        lines = res.stdout_text.splitlines()
        if len(lines) == 1:
            first_status = final_status = lines[0]
        else:
            first_status = lines[0]
            final_status = lines[-1]
            self.assertIn("'status': 'started'", first_status)
            self.assertIn("'id': 1", first_status)
        self.assertIn("'id': 1", first_status)
        self.assertIn("'status': 'finished'", final_status)
        self.assertEqual(res.exit_status, 0)

    @skipUnlessPathExists("/bin/echo")
    def test_recipe_exec_test_2(self):
        recipe = os.path.join(
            BASEDIR,
            "examples",
            "nrunner",
            "recipes",
            "tasks",
            "exec-test",
            "2-echo.json",
        )
        cmd = f"{RUNNER} task-run-recipe {recipe}"
        res = process.run(cmd, ignore_status=True)
        lines = res.stdout_text.splitlines()
        if len(lines) == 1:
            first_status = final_status = lines[0]
        else:
            first_status = lines[0]
            stdout_status = lines[-3]
            final_status = lines[-1]
            self.assertIn("'status': 'started'", first_status)
            self.assertIn("'id': 2", first_status)
        self.assertIn("'id': 2", first_status)
        self.assertIn("'status': 'finished'", final_status)
        self.assertIn("'log': b'avocado'", stdout_status)
        self.assertEqual(res.exit_status, 0)

    @skipUnlessPathExists("/bin/sleep")
    def test_recipe_exec_test_3(self):
        recipe = os.path.join(
            BASEDIR,
            "examples",
            "nrunner",
            "recipes",
            "tasks",
            "exec-test",
            "3-sleep.json",
        )
        cmd = f"{RUNNER} task-run-recipe {recipe}"
        res = process.run(cmd, ignore_status=True)
        lines = res.stdout_text.splitlines()
        # based on the :data:`avocado.core.nrunner.RUNNER_RUN_STATUS_INTERVAL`
        # this runnable should produce multiple status lines
        self.assertGreater(len(lines), 1)
        first_status = lines[0]
        self.assertIn("'status': 'started'", first_status)
        self.assertIn("'id': 3", first_status)
        final_status = lines[-1]
        self.assertIn("'id': 3", first_status)
        self.assertIn("'status': 'finished'", final_status)
        self.assertEqual(res.exit_status, 0)


class ResolveSerializeRun(TestCaseTmpDir):
    @skipUnlessPathExists("/bin/true")
    def test(self):
        cmd = "%s list --write-recipes-to-directory=%s -- /bin/true"
        cmd %= (AVOCADO, self.tmpdir.name)
        res = process.run(cmd)
        self.assertEqual(b"exec-test /bin/true\n", res.stdout)
        cmd = "%s runnable-run-recipe %s"
        cmd %= (RUNNER, os.path.join(self.tmpdir.name, "1.json"))
        res = process.run(cmd)
        self.assertIn(b"'status': 'finished'", res.stdout)
