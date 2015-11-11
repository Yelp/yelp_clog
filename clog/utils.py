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

# -*- coding: utf-8 -*-
import bz2
import gzip
import re

DISALLOWED_STREAM_CHARACTERS_RE = re.compile(r'[^-_a-zA-Z0-9]')


def scribify(stream_name):
    """Convert an arbitrary stream name to be appropriate to use as a Scribe category name."""
    return DISALLOWED_STREAM_CHARACTERS_RE.sub('_', stream_name)


def open_compressed_file(filename, mode='r'):
    """Open a file as raw, gzip, or bz2, based on the filename."""
    if filename.endswith('.bz2'):
        return bz2.BZ2File(filename, mode=mode)
    elif filename.endswith('.gz'):
        return gzip.GzipFile(filename, mode=mode)
    else:
        return open(filename, mode=mode)
