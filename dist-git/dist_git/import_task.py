# coding: utf-8

import json

from exceptions import PackageImportException

class ImportTask(object):
    def __init__(self):
        self.build_id = None
        self.owner = None
        self.project = None
        self.branches = []
        self.srpm_url = None

    @staticmethod
    def from_dict(task_dict):
        task = ImportTask()

        try:
            task.build_id = task_dict["build_id"]
            task.owner = task_dict["owner"]
            task.project = task_dict["project"]
            task.branches = task_dict["branches"]
            task.srpm_url = task_dict["srpm_url"]
        except (KeyError, ValueError) as e:
            raise PackageImportException(str(e))

        return task

    @property
    def repo_namespace(self):
        return "{}/{}".format(self.owner, self.project)
