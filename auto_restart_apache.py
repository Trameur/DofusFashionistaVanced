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

import datetime
import socket
import urllib.request, urllib.error, urllib.parse
from subprocess import call

def is_localhost_down():
    try:
        home_page = urllib.request.urlopen('https://dofusfashionista.gg', timeout=120)
        first_bytes = home_page.read(200)
        if first_bytes:
            # print_with_time('Home page ok.')
            return False
        else:
            print_with_time('Empty response.')
            return True
    except (urllib.error.URLError, socket.timeout, socket.error) as e:
        print_with_time(str(e))
        return True

def main():
    is_down = is_localhost_down()
    if is_down:
        print_with_time('Restarting apache because server is down.')
        call(['/etc/init.d/apache2', 'restart'])

def print_with_time(s):
    print('[%s]' % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
    print(s)

if __name__ == '__main__':
    main()
