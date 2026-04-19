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

from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings
from django.urls import reverse
import requests
from chardata.models import ContactForm
from django.core.mail import send_mail, BadHeaderError
from smtplib import SMTPException
from chardata.util import set_response
import logging

logger = logging.getLogger(__name__)

def contact(request):
    return set_response(request,
                        'chardata/contacts.html',
                        {'form': ContactForm()})

def send_email(request):
    if request.method != 'POST':
        return HttpResponseRedirect(reverse('contact'))

    subject = request.POST.get('topic', '')
    message = request.POST.get('message', '')
    from_email = request.POST.get('email', '')
    name = request.POST.get('name', '')
    g_recaptcha_response = request.POST.get('g-recaptcha-response', '')

    recaptcha_secret = settings.GEN_CONFIGS.get('url_captcha_secret')
    recaptcha_ok = False

    # Allow testing environments (DEBUG=True) to submit without captcha.
    if settings.DEBUG:
        recaptcha_ok = True
    else:
        url = "https://www.google.com/recaptcha/api/siteverify"
        data = {
            'secret': recaptcha_secret,
            'response': g_recaptcha_response
        }
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            recaptcha_result = response.json()
            recaptcha_ok = bool(recaptcha_result.get('success'))
        except (requests.RequestException, ValueError) as e:
            logger.warning('Contact form captcha verification failed: %s', e)
            recaptcha_ok = False

    if not recaptcha_ok:
        return HttpResponseRedirect(reverse('nomessage'))

    try:
        send_mail(
            "Fashionista Form: " + subject,
            message + "\n\nfrom: " + name + "\n" + from_email,
            'DofusFashionistaVanced@gmail.com',
            ['DofusFashionistaVanced@gmail.com']
        )
    except (BadHeaderError, SMTPException, OSError) as e:
        logger.error('Contact form email send failed: %s', e)
        return HttpResponseRedirect(reverse('nomessage'))

    return HttpResponseRedirect(reverse('thankyou'))
        
def thankyou(request):
    return set_response(request,
                        'chardata/thankyou.html',
                        {})
def nomessage(request):
    return set_response(request,
                        'chardata/nomessage.html',
                        {})
