# -*- coding: utf-8 -*-

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

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponseRedirect
from django.conf import settings
from django.urls import reverse
from chardata.models import ContactForm
from django.core.mail import send_mail, BadHeaderError
from smtplib import SMTPException
from chardata.util import set_response, version_reverse, recaptcha_ok
import logging

logger = logging.getLogger(__name__)

def contact(request):
    # Empty for an anonymous reader, and for an account that carries no address
    # of its own; the template falls back to the two plain fields there.
    known_email = ''
    if request.user.is_authenticated:
        known_email = (request.user.email or '').strip()
    return set_response(request,
                        'chardata/contacts.html',
                        {'form': ContactForm(),
                         'known_email': known_email})

# ContactForm declares every field required and this view never used it, so an
# empty submission arrived as "Fashionista Form:" with an empty body.
MAX_SUBJECT = 200
MAX_NAME = 100
MAX_EMAIL = 254
MAX_MESSAGE = 10000  # the textarea's own maxlength

NO_NAME = '(no name given)'
NO_ADDRESS = '(no address given)'


def send_email(request):
    if request.method != 'POST':
        return HttpResponseRedirect(version_reverse(request, 'contact'))

    subject = request.POST.get('topic', '').strip()
    message = request.POST.get('message', '').strip()
    from_email = request.POST.get('email', '').strip()
    name = request.POST.get('name', '').strip()

    if not subject or not message:
        return HttpResponseRedirect(version_reverse(request, 'nomessage'))
    if (len(subject) > MAX_SUBJECT or len(message) > MAX_MESSAGE
            or len(name) > MAX_NAME or len(from_email) > MAX_EMAIL):
        return HttpResponseRedirect(version_reverse(request, 'nomessage'))

    # A typo in the address is no reason to drop somebody's message; say in the
    # mail itself that there is no way to answer it.
    reply_to = NO_ADDRESS
    if from_email:
        reply_to = from_email
        try:
            validate_email(from_email)
        except ValidationError:
            reply_to = '%s (not a usable address)' % from_email

    if not settings.DEBUG and not recaptcha_ok(request):
        return HttpResponseRedirect(reverse('nomessage'))

    try:
        send_mail(
            "Fashionista Form: " + subject,
            message + "\n\nfrom: " + (name or NO_NAME) + "\n" + reply_to,
            'DofusFashionistaVanced@gmail.com',
            ['DofusFashionistaVanced@gmail.com']
        )
    except (BadHeaderError, SMTPException, OSError) as e:
        logger.error('Contact form email send failed: %s', e)
        return HttpResponseRedirect(version_reverse(request, 'nomessage'))

    return HttpResponseRedirect(version_reverse(request, 'thankyou'))
        
def thankyou(request):
    return set_response(request,
                        'chardata/thankyou.html',
                        {})
def nomessage(request):
    return set_response(request,
                        'chardata/nomessage.html',
                        {})
