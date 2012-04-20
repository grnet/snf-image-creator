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

from kamaki.config import Config
from kamaki.clients import ClientError
from kamaki.clients.image import ImageClient
from kamaki.clients.pithos import PithosClient

from image_creator.util import FatalError, progress

CONTAINER = "images"


class Kamaki:
    def __init__(self, account, token):
        self.account = account
        self.token = token

        config = Config()

        pithos_url = config.get('storage', 'url')
        self.container = CONTAINER
        self.pithos_client = PithosClient(pithos_url, token, self.account,
                                                                self.container)

        image_url = config.get('image', 'url')
        self.image_client = ImageClient(image_url, token)

        self.uploaded_object = None

    def upload(self, filename, size=None, remote_path=None):

        if remote_path is None:
            remote_path = basename(filename)

        with open(filename) as f:
            try:
                self.pithos_client.create_container(self.container)
            except ClientError as e:
                if e.status != 202:  # Ignore container already exists errors
                    raise FatalError("Pithos client: %d %s" % \
                                                        (e.status, e.message))
            try:
                hash_progress = progress("(1/2)  Calculating block hashes:")
                upload_progress = progress("(2/2)  Uploading missing blocks:")
                self.pithos_client.create_object(remote_path, f, size,
                                                hash_progress, upload_progress)
                self.uploaded_object = "pithos://%s/%s/%s" % \
                                (self.account, self.container, remote_path)
            except ClientError as e:
                raise FatalError("Pithos client: %d %s" % \
                                                        (e.status, e.message))

    def register(self, metadata):
        pass

# vim: set sta sts=4 shiftwidth=4 sw=4 et ai :
