# Copyright 2015 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import boto
import boto.s3
import boto.s3.connection
import datetime
import logging
import re
import sys
import zlib

import six

# THIS MUST END IN A /
S3PREFIX = "logs/"
S3_KEY_RE = re.compile(r'.*/(?P<stream_name>[\w-]+)/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/.+(?P<gz>\.gz)?$')


#----------------------- SCRIBE LOG CHUNK OBJECTS -----------------------#

class BadKeyError(Exception):
    def __init__(self, key, keytype=""):
        self.key = key
        self.keytype = keytype

    def __repr__(self):
        return "<BadKeyError %s:%s>" % (self.keytype, self.key)

    def __str__(self):
        return "BadKeyError: %s key %s did not match the expected format" % (self.keytype, self.key)


class ScribeFile(object):
    """Base class for Scribe file objects. These represent a single log chunk,
    and can be read or listed. Scribe File objects are equal if the combination of
    their date, stream name, and aggregator are the same. This allows you to, for example,
    create a set of files from both s3 and a local cache without reading the same
    chunk twice.

    Important methods:
        read: adds a file's contents to the stream ostream, transparently handling gzip'd data

    Properties:
        sort_key: A key to sort or compare with
        size: The length of the record in bytes
    """
    def __init__(self, stream_name, year, month, day):
        self.stream_name = stream_name
        self.year = year
        self.month = month
        self.day = day
        self.date = datetime.date(self.year, self.month, self.day)

    @property
    def size(self):
        raise NotImplementedError

    def read(self, ostream=sys.stdout):
        raise NotImplementedError

    def read_orig(self, ostream=sys.stdout):
        raise NotImplementedError


class ScribeS3File(ScribeFile):
    """Represent scribe log chunks on S3"""
    def __init__(self, key):
        self.key = key
        keymd = S3_KEY_RE.match(key.name)
        if not keymd:
            raise BadKeyError(key, "S3")
        super(ScribeS3File, self).__init__(
            keymd.group('stream_name'),
            int(keymd.group('year')),
            int(keymd.group('month')),
            int(keymd.group('day')),
        )

    def read(self, ostream=sys.stdout):
        """Read self into the ostream"""
        decompressor = zlib.decompressobj(31)
        # Python 2 works with string, python 3 with bytes
        remainder = "" if six.PY2 else b""
        if self.key.name.endswith(".gz"):
            for data in self.key:
                remainder += data
                try:
                    ostream.write(decompressor.decompress(remainder))
                    remainder = decompressor.unconsumed_tail
                except zlib.error:
                    # maybe we didn't have enough data in this chunk to
                    # decompress any. if so, build up a string to decompress
                    pass
        else:
            for data in self.key:
                ostream.write(data)
        if len(remainder) > 0:
            logging.error("Encountered %d extra bits in zlib output", len(remainder))

    def read_orig(self, ostream=sys.stdout):
        """Read the original of self (compressed if applicable) to ostream"""
        self.key.get_contents_to_file(ostream)

    @property
    def size(self):
        return self.key.size


#----------------------- SCRIBE CONNECTION MANAGERS -----------------------#

class ScribeS3(object):
    """This class represents an S3 connection and abstracts scribe interactions"""

    LOGS_BASE_PATH = "{prefix}{stream}/{year:=04d}/{month:=02d}/{day:=02d}"
    LOG_FILE_PATH = LOGS_BASE_PATH + "/{aggregator}-{part:=05d}.gz"
    COMPLETE_FILE_PATH = LOGS_BASE_PATH + "/COMPLETE"

    def __init__(
        self,
        s3_host,
        aws_access_key_id,
        aws_secret_access_key,
        s3_bucket,
        s3_key_prefix=None,
    ):
        self.s3_key_prefix = s3_key_prefix
        if self.s3_key_prefix and self.s3_key_prefix[-1] != '/':
            self.s3_key_prefix += '/'
        self.s3_connection = boto.s3.connection.S3Connection(
            host=s3_host,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.s3_bucket = self.s3_connection.get_bucket(s3_bucket)
        logging.debug('connected to s3 with %s', self.s3_connection)

    @property
    def streams(self):
        ret = set()
        for prefix in self.s3_bucket.list(prefix=self.s3_key_prefix, delimiter="/"):
            prefix = prefix.name.replace(self.s3_key_prefix or S3PREFIX, "", 1).rstrip('/')
            ret.add(prefix)
        return ret

    def complete_for(self, stream_name, date):
        """Are the S3 uploads for the given stream_name on the given date marked as complete?"""
        complete_key_name = self.COMPLETE_FILE_PATH.format(
            prefix=self.s3_key_prefix,
            stream=stream_name,
            year=date.year,
            month=date.month,
            day=date.day,
        )
        key = self.s3_bucket.get_key(complete_key_name)
        return bool(key)

    def get_logs(self, stream_name, date):
        prefix = self.LOGS_BASE_PATH.format(
            prefix=self.s3_key_prefix,
            stream=stream_name,
            year=date.year,
            month=date.month,
            day=date.day,
        )
        ret = set()
        for s3_name in self.s3_bucket.list(prefix=prefix):
            if s3_name.name.endswith("COMPLETE"):
                continue
            if s3_name.name.endswith("_SUCCESS"):
                continue
            if s3_name.name.endswith(".bad"):
                continue
            ret.add(ScribeS3File(s3_name))
        return ret

    def get_log(self, stream_name, date, aggregator, part):
        """Get a specific log

        .. warning:: This function is deprecated and should not be used.
        """
        key_name = self.LOG_FILE_PATH.format(
            prefix=self.s3_key_prefix,
            stream=stream_name,
            year=date.year,
            month=date.month,
            day=date.day,
            aggregator=aggregator,
            part=part,
        )
        key = self.s3_bucket.get_key(key_name)
        if key:
            return ScribeS3File(key)
        return None


#----------------------- COMMAND OBJECTS -----------------------#

class ScribeReader(object):
    """
    ScribeReader provides an interface for interacting with individual log elements
    (ScribeFile objects) in Scribe
    """
    def __init__(self, stream_name, s3_connections=None, fs_connection=None, ostream=sys.stdout, not_in_s3=False):
        """Initialize the ScribeReader

        Args:
            stream_name: The stream to read from
            s3_connections: Optionally, an iterable of ScribeS3 objects
            fs_connection: Optionally, a ScribeFS object
            not_in_s3: Remove only keys unique to the fs_connection

        Will read from s3_connection and/or fs_connection, depending on which are provided
        """
        self.stream_name = stream_name
        self.s3_connections = s3_connections
        self.fs_connection = fs_connection
        self.ostream = ostream
        self.not_in_s3 = not_in_s3

    def logs_for_date(self, date):
        """Write to the initial ostream for the given date"""
        keys = set()
        if self.fs_connection:
            keys |= self.fs_connection.get_logs(self.stream_name, date)
        if self.s3_connections:
            for connection in self.s3_connections:
                if connection is None:
                    continue
                s3_keys = connection.get_logs(self.stream_name, date)
                if self.not_in_s3:
                    keys -= s3_keys
                else:
                    keys |= s3_keys
        return sorted(keys, key=lambda key: key.key.last_modified)

    def get_for_date(self, date):
        for key in self.logs_for_date(date):
            key.read(ostream=self.ostream)
            yield
