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

from os.path import basename

from kamaki.cli.config import Config
from kamaki.clients import ClientError
from kamaki.clients.image import ImageClient
from kamaki.clients.pithos import PithosClient
from kamaki.clients.astakos import AstakosClient


class Kamaki(object):

    CONTAINER = "images"

    @staticmethod
    def get_token():
        """Get the saved token"""
        config = Config()
        return config.get('global', 'token')

    @staticmethod
    def save_token(token):
        """Save this token to the configuration file"""
        config = Config()
        config.set('global', 'token', token)
        config.write()

    @staticmethod
    def get_account(token):
        """Return the account corresponding to this token"""
        config = Config()
        astakos = AstakosClient(config.get('user', 'url'), token)
        try:
            account = astakos.info()
        except ClientError as e:
            if e.status == 401:  # Unauthorized: invalid token
                return None
            else:
                raise
        return account

    def __init__(self, account, output):
        """Create a Kamaki instance"""
        self.account = account
        self.out = output

        config = Config()

        pithos_url = config.get('file', 'url')
        self.pithos_client = PithosClient(
            pithos_url, self.account['auth_token'], self.account['uuid'],
            self.CONTAINER)

        image_url = config.get('image', 'url')
        self.image_client = ImageClient(image_url, self.account['auth_token'])

    def upload(self, file_obj, size=None, remote_path=None, hp=None, up=None):
        """Upload a file to pithos"""

        path = basename(file_obj.name) if remote_path is None else remote_path

        try:
            self.pithos_client.create_container(self.CONTAINER)
        except ClientError as e:
            if e.status != 202:  # Ignore container already exists errors
                raise e

        hash_cb = self.out.progress_generator(hp) if hp is not None else None
        upload_cb = self.out.progress_generator(up) if up is not None else None

        self.pithos_client.upload_object(path, file_obj, size, hash_cb,
                                         upload_cb)

        return "pithos://%s/%s/%s" % (self.account['uuid'], self.CONTAINER,
                                      path)

    def register(self, name, location, metadata, public=False):
        """Register an image to ~okeanos"""

        # Convert all metadata to strings
        str_metadata = {}
        for (key, value) in metadata.iteritems():
            str_metadata[str(key)] = str(value)
        is_public = 'true' if public else 'false'
        params = {'is_public': is_public, 'disk_format': 'diskdump'}
        self.image_client.register(name, location, params, str_metadata)

    def object_exists(self, location):
        """Check if an object exists in pythos"""

        try:
            self.pithos_client.get_object_info(location)
        except ClientError as e:
            if e.status == 404:  # Object not found error
                return False
            else:
                raise
        return True

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
