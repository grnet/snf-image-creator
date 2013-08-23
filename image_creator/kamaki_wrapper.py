# -*- coding: utf-8 -*-
#
# Copyright 2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

"""This modules provides the interface for working with the ./kamaki library.
The library is used to upload images to and register them with a Synnefo
deployment.
"""

import sys

from os.path import basename

from kamaki.cli.config import Config
from kamaki.clients import ClientError
from kamaki.clients.image import ImageClient
from kamaki.clients.pithos import PithosClient
from kamaki.clients.astakos import AstakosClient

try:
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
        """Returns a dict with cloud info"""
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
        """Deletes an existing cloud from the Kamaki configuration file"""
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
        """Upload a file to pithos"""

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
        """Register an image with cyclades"""

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
        """Check if an object exists in pythos"""

        try:
            self.pithos.get_object_info(location)
        except ClientError as e:
            if e.status == 404:  # Object not found error
                return False
            else:
                raise
        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
