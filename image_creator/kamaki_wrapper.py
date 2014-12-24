# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2014 GRNET S.A.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""This modules provides the interface for working with the ./kamaki library.
The library is used to upload images to and register them with a Synnefo
deployment.
"""

import sys
import logging

from os.path import basename

from kamaki.cli.config import Config
from kamaki.clients import ClientError
from kamaki.clients.image import ImageClient
from kamaki.clients.pithos import PithosClient
from kamaki.clients.astakos import CachedAstakosClient as AstakosClient

try:
    from kamaki.clients.utils import https
    https.patch_ignore_ssl()
except ImportError:
    pass

try:
    logger = logging.getLogger("kamaki.cli.config")
    logger.setLevel(logging.ERROR)
    config = Config()
except Exception as e:
    sys.stderr.write("Kamaki config error: %s\n" % str(e))
    sys.exit(1)


class Kamaki(object):
    """Wrapper class for the ./kamaki library"""
    CONTAINER = "images"

    @staticmethod
    def get_default_cloud_name():
        """Returns the name of the default cloud"""
        clouds = config.keys('cloud')
        default = config.get('global', 'default_cloud')
        if not default:
            return clouds[0] if len(clouds) else ""
        return default if default in clouds else ""

    @staticmethod
    def set_default_cloud(name):
        """Sets a cloud account as default"""
        config.set('global', 'default_cloud', name)
        config.write()

    @staticmethod
    def get_clouds():
        """Returns the list of available clouds"""
        names = config.keys('cloud')

        clouds = {}
        for name in names:
            clouds[name] = config.get('cloud', name)

        return clouds

    @staticmethod
    def get_cloud_by_name(name):
        """Returns a dictionary with cloud info"""
        return config.get('cloud', name)

    @staticmethod
    def save_cloud(name, url, token, description=""):
        """Save a new cloud account"""
        cloud = {'url': url, 'token': token}
        if len(description):
            cloud['description'] = description
        config.set('cloud', name, cloud)

        # Make the saved cloud the default one
        config.set('global', 'default_cloud', name)
        config.write()

    @staticmethod
    def remove_cloud(name):
        """Deletes an existing cloud from the ./Kamaki configuration file"""
        config.remove_option('cloud', name)
        config.write()

    @staticmethod
    def create_account(url, token):
        """Given a valid (URL, tokens) pair this method returns an Astakos
        client instance
        """
        client = AstakosClient(url, token)
        try:
            client.authenticate()
        except ClientError:
            return None

        return client

    @staticmethod
    def get_account(cloud_name):
        """Given a saved cloud name this method returns an Astakos client
        instance
        """
        cloud = config.get('cloud', cloud_name)
        assert cloud, "cloud: `%s' does not exist" % cloud_name
        assert 'url' in cloud, "url attr is missing in %s" % cloud_name
        assert 'token' in cloud, "token attr is missing in %s" % cloud_name

        return Kamaki.create_account(cloud['url'], cloud['token'])

    def __init__(self, account, output):
        """Create a Kamaki instance"""
        self.account = account
        self.out = output

        self.pithos = PithosClient(
            self.account.get_service_endpoints('object-store')['publicURL'],
            self.account.token,
            self.account.user_info()['id'],
            self.CONTAINER)

        self.image = ImageClient(
            self.account.get_service_endpoints('image')['publicURL'],
            self.account.token)

    def upload(self, file_obj, size=None, remote_path=None, hp=None, up=None):
        """Upload a file to Pithos+"""

        path = basename(file_obj.name) if remote_path is None else remote_path

        try:
            self.pithos.create_container(self.CONTAINER)
        except ClientError as e:
            if e.status != 202:  # Ignore container already exists errors
                raise e

        hash_cb = self.out.progress_generator(hp) if hp is not None else None
        upload_cb = self.out.progress_generator(up) if up is not None else None

        self.pithos.upload_object(path, file_obj, size, hash_cb, upload_cb)

        return "pithos://%s/%s/%s" % (self.account.user_info()['id'],
                                      self.CONTAINER, path)

    def register(self, name, location, metadata, public=False):
        """Register an image with Cyclades"""

        # Convert all metadata to strings
        str_metadata = {}
        for (key, value) in metadata.iteritems():
            str_metadata[str(key)] = str(value)
        is_public = 'true' if public else 'false'
        params = {'is_public': is_public, 'disk_format': 'diskdump'}
        return self.image.register(name, location, params, str_metadata)

    def share(self, location):
        """Share this file with all the users"""

        self.pithos.set_object_sharing(location, "*")

    def object_exists(self, location):
        """Check if an object exists in Pithos+"""

        try:
            self.pithos.get_object_info(location)
        except ClientError as e:
            if e.status == 404:  # Object not found error
                return False
            else:
                raise
        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
