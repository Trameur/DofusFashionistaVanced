#!/usr/bin/env python

# Copyright (C) 2020 The Dofus Fashionista
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from subprocess import call
import datetime
import json
import os
import platform
import subprocess
import sys
import time

import s3_fashionista

if sys.platform == 'win32':
    CONFIG_DIR = os.path.join(os.environ.get('APPDATA', ''), 'fashionista')
else:
    CONFIG_DIR = '/etc/fashionista'
CONFIG_DIR = os.environ.get('FASHIONISTA_CONFIG_DIR', CONFIG_DIR)

TEMP_LOCATION = '/tmp/'
DBBACKUP_S3_BUCKET = 'fashionista-dbbackup'
MYSQL_DB_NAME = 'fashionista'

#: A dump of this database runs to hundreds of megabytes. Anything this
#: small is an error message, not a backup.
MINIMUM_DUMP_BYTES = 1024 * 1024

def mysql_connection():
    """Where the site itself keeps its database.

    mysqldump used to be called with the database name alone, which reaches a
    local socket. The database has had its own container since the site moved
    to Docker, so there was no socket to reach: every run since then failed to
    connect, and the guard below turned that into a loud error instead of an
    empty backup. Reading the settings the site reads keeps the two in step.
    """
    stored = {}
    try:
        with open(os.path.join(CONFIG_DIR, 'gen_config.json')) as handle:
            stored = json.loads(handle.read())
    except (OSError, ValueError):
        pass
    return {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', '3306'),
        'name': os.environ.get('DB_NAME', MYSQL_DB_NAME),
        'user': os.environ.get('DB_USER', stored.get('mysql_USER', 'root')),
        'password': os.environ.get('DB_PASSWORD',
                                   stored.get('mysql_PASSWORD', '')),
    }


def dump_database(path):
    """Write the dump, and refuse to go further on a failed one.

    `os.system` used to run mysqldump and its exit status was never read: a
    refused connection or a missing grant wrote a short file, and the run went
    on to upload it. A backup that restores to nothing is worse than no backup,
    because it is trusted.
    """
    where = mysql_connection()
    command = ['mysqldump',
               '--host', where['host'], '--port', str(where['port']),
               '--user', where['user'],
               # A live site is writing while this runs. Without it the dump
               # mixes rows from before and after a transaction.
               '--single-transaction',
               where['name']]
    environment = dict(os.environ)
    if where['password']:
        # Never as --password=: the command line of a running process is
        # readable by anyone with a shell on the machine.
        environment['MYSQL_PWD'] = where['password']
    with open(path, 'wb') as out:
        code = subprocess.call(command, stdout=out, env=environment)
    if code != 0:
        raise RuntimeError('mysqldump exited %d; nothing was backed up' % code)
    size = os.path.getsize(path)
    if size < MINIMUM_DUMP_BYTES:
        raise RuntimeError('the dump is %d bytes, under the %d expected of a '
                           'real database; nothing was backed up'
                           % (size, MINIMUM_DUMP_BYTES))
    return size


def upload(bucket, local_path, key_name):
    """Send the file with the API boto3 actually has.

    This used to call `bucket.new_key(...).set_contents_from_filename(...)`,
    which is boto2. `s3_fashionista.get_s3_bucket` returns a boto3 Bucket, and
    a boto3 Bucket has four actions -- Create, Delete, DeleteObjects, PutObject
    -- and no `new_key`. So every run raised AttributeError after dumping and
    gzipping, and no backup ever reached the bucket.
    """
    if bucket is None:
        raise RuntimeError('no S3 bucket: credentials are not configured, '
                           'so the dump was written but never sent')
    bucket.upload_file(local_path, key_name, Callback=_update_progress)


def main():
    print('[%s]' % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))

    backup_file_radical = _get_filename()
    backup_file = backup_file_radical + '.dump'
    backup_file_path = TEMP_LOCATION + backup_file
    backup_file_zipped = backup_file + '.gz'
    backup_file_zipped_path = TEMP_LOCATION + backup_file_zipped

    try:
        print('Writing backup file to %s' % backup_file_path)
        size = dump_database(backup_file_path)
        print('Dumped %d bytes' % size)

        print('GZipping to %s' % backup_file_zipped)
        call(['gzip', backup_file_path])

        print('Uploading to S3 bucket %s' % DBBACKUP_S3_BUCKET)
        upload(s3_fashionista.get_s3_bucket(DBBACKUP_S3_BUCKET),
               backup_file_zipped_path, backup_file_zipped)
        print('Uploaded %s' % backup_file_zipped)
    finally:
        # The cleanup used to sit after the upload, so a failed run left its
        # dump in /tmp and the next one added another.
        for leftover in (backup_file_path, backup_file_zipped_path):
            if os.path.exists(leftover):
                print('Deleting %s' % leftover)
                os.remove(leftover)

def _get_filename():
    return 'backup-%s-%s' % (platform.node(),
                             time.strftime("%Y-%m-%d-%H-%M-%S"))

def _update_progress(so_far):
    """boto3 hands the callback one number, the bytes sent so far."""
    print('%d bytes transferred' % so_far)

if __name__ == '__main__':
    main()
