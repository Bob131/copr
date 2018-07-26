from __future__ import absolute_import

import os
from . import BaseProxy
from ..requests import Request, FileRequest, POST


class ProjectChrootProxy(BaseProxy):

    def get(self, ownername, projectname, chrootname):
        """
        Return a configuration of a chroot in a project

        :param str ownername:
        :param str projectname:
        :param str chrootname:
        :return: Munch
        """
        endpoint = "/project-chroot"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return response.munchify()

    def get_build_config(self, ownername, projectname, chrootname):
        """
        Return a build configuration of a chroot in a project

        :param str ownername:
        :param str projectname:
        :param str chrootname:
        :return: Munch
        """
        endpoint = "/project-chroot/build-config"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }
        request = Request(endpoint, api_base_url=self.api_base_url, params=params)
        response = request.send()
        return response.munchify()

    def edit(self, ownername, projectname, chrootname, packages=None, repos=None, comps=None, delete_comps=False):
        """
        Edit a chroot configuration in a project

        :param str ownername:
        :param str projectname:
        :param str chrootname:
        :param list packages: buildroot packages for the chroot
        :param list repos: buildroot additional repos
        :param str comps: file path to the comps.xml file
        :param bool delete_comps: if True, current comps.xml will be removed
        :return: Munch
        """
        endpoint = "/project-chroot/edit"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "chrootname": chrootname,
        }
        data = {
            "repos": " ".join(repos or []),
            "buildroot_pkgs": " ".join(packages or []),
            "delete_comps": delete_comps,
        }
        files = {}
        if comps:
            comps_f = open(comps, "rb")
            files["upload_comps"] = (os.path.basename(comps_f.name), comps_f, "application/text")

        request = FileRequest(endpoint, api_base_url=self.api_base_url, method=POST,
                              params=params, data=data, files=files, auth=self.auth)
        response = request.send()
        return response.munchify()
