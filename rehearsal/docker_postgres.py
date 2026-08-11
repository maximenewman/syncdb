import shutil
import subprocess
import time
import uuid


class DockerUnavailable(RuntimeError):
    """Docker is not installed, or its daemon is not answering."""


def _docker(*args, check=True, timeout=120):
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )


def require_docker() -> str:
    """Return the Docker server version, or raise DockerUnavailable."""
    if shutil.which("docker") is None:
        raise DockerUnavailable("docker is not on PATH")
    try:
        result = _docker("info", "--format", "{{.ServerVersion}}", timeout=60)
    except subprocess.CalledProcessError as error:
        raise DockerUnavailable(
            f"docker is installed but the daemon is not responding: "
            f"{error.stderr.strip()}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise DockerUnavailable("docker daemon did not respond within 60s") from error
    return result.stdout.strip()


class DisposablePostgres:
    """
    A throwaway Postgres container used to rehearse a migration.

    Context manager: starts the container on enter, removes it on exit even
    if the rehearsal failed, unless keep=True.
    """

    def __init__(self, image="postgres:16", port=15432, password="rehearsal",
                 user="syncdb", database="rehearsal", keep=False):
        self.image = image
        self.port = port
        self.password = password
        self.user = user
        self.database = database
        self.keep = keep
        self.name = f"syncdb-rehearsal-{uuid.uuid4().hex[:8]}"

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg://{self.user}:{self.password}"
            f"@127.0.0.1:{self.port}/{self.database}"
        )

    def __enter__(self):
        require_docker()
        print(f"starting {self.image} as {self.name} on port {self.port}")
        _docker(
            "run", "-d",
            "--name", self.name,
            "-e", f"POSTGRES_PASSWORD={self.password}",
            "-e", f"POSTGRES_USER={self.user}",
            "-e", f"POSTGRES_DB={self.database}",
            "-p", f"{self.port}:5432",
            self.image,
            timeout=600,
        )
        self._wait_ready()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.keep:
            print(f"container {self.name} left running on port {self.port}")
            print(f"  remove it with: docker rm -f {self.name}")
            return False
        _docker("rm", "-f", self.name, check=False)
        print(f"removed container {self.name}")
        return False

    def _wait_ready(self, timeout=120):
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = _docker(
                "exec", self.name,
                "pg_isready", "-U", self.user, "-d", self.database,
                check=False,
                timeout=30,
            )
            if result.returncode == 0:
                print("container is accepting connections")
                return
            time.sleep(1)
        raise DockerUnavailable(
            f"{self.name} did not accept connections within {timeout}s"
        )

    def apply_sql(self, sql: str) -> None:
        """Run a DDL script, failing on the first error rather than limping on."""
        result = subprocess.run(
            [
                "docker", "exec", "-i", "-e", f"PGPASSWORD={self.password}",
                self.name, "psql",
                "-U", self.user, "-d", self.database,
                "-v", "ON_ERROR_STOP=1", "-q", "-f", "-",
            ],
            input=sql,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"schema failed to apply: {result.stderr.strip()}")
