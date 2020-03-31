import logging
import subprocess
from os import path
from pathlib import Path

from erdpy import dependencies, errors, myprocess, utils
from erdpy.projects.project_base import Project

logger = logging.getLogger("ProjectRust")


class ProjectRust(Project):
    def __init__(self, directory):
        super().__init__(directory)
        self.cargo_file = self._get_cargo_file()

    def _get_cargo_file(self):
        cargo_path = path.join(self.directory, "Cargo.toml")
        return CargoFile(cargo_path)

    def perform_build(self):
        try:
            self.run_cargo()
        except subprocess.CalledProcessError as err:
            raise errors.BuildError(err.output)

    def run_cargo(self):
        if self.debug:
            args = ["cargo", "build"]
        else:
            args = [
                "cargo",
                "build",
                "--manifest-path",
                self.cargo_file.path,
                "--target=wasm32-unknown-unknown",
                "--release"
            ]

        myprocess.run_process_async(args, env=self._get_env())

    def get_file_wasm(self):
        return Path(self.directory, "target", "wasm32-unknown-unknown", "release", "wasm.wasm")

    def get_wasm_path(self):
        pass

    def get_dependencies(self):
        return ["rust"]

    def _get_env(self):
        return dependencies.get_module_by_key("rust").get_env()


class CargoFile:
    def __init__(self, path):
        self.path = path

        try:
            self._parse_file()
        except Exception:
            raise errors.BuildError("Can't read cargo file.")

    def _parse_file(self):
        self.data = utils.read_toml_file(self.path)

    @property
    def package_name(self):
        return self.data["package"]["name"]

    @package_name.setter
    def package_name(self, value):
        self.data["package"]["name"] = value


    @property
    def bin_name(self):
        return self.data["bin"][0]["name"]

    @bin_name.setter
    def bin_name(self, value):
        self.data["bin"][0]["name"] = value

    def save(self):
        utils.write_toml_file(self.path, self.data)
