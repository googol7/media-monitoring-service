#! /usr/bin/env python2
# -*- coding: utf-8 -*-
"""
   Media Monitoring Service
   Copyright (c) 2021 Philipp Metzler
"""

from datetime import date
import urllib2
# For Python3:
# from urllib.request import urlopen
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
# from decouple import config
from settings import (EMAIL_FROM, EMAIL_TO, SMTP_SERVER, SMTP_USER,
                      SMTP_PASSWORD, KEYWORDS)

highlights = []

"""
Test with this regex online tool: https://regex101.com/
"""


def get_html(url, needle, start_identifier=None, end_identifier=None):
    response = urllib2.urlopen(url)
    html = response.read()

    if (start_identifier is not None) and (end_identifier is not None):
        start_pos = html.find(start_identifier)
        end_pos = html.find(end_identifier)
        html = html[start_pos:end_pos]

    # re.DOTALL
    # Make the '.' special character match any character at all, including a
    # newline without this flag, '.' will match anything except a newline.
    # https://docs.python.org/2/library/re.html#re.DOTALL

    return re.findall(needle, html, re.DOTALL | re.IGNORECASE)


def decode_js_text(text):
    # \&quot;Animalicum\&quot;
    # \u00fc
    # \"

    # https://stackoverflow.com/questions/4020539/process-escape-sequences-in-a-string-in-python/24519338

    try:
        # Python 2.6-2.7
        from HTMLParser import HTMLParser
    except ImportError:
        # Python 3
        from html.parser import HTMLParser

    # TODO: Python 3
    # import html
    # text = html.unescape(text)  # &quot; -> "

    text = text.replace('null', '')
    text = text.replace('&quot;', '"')

    text = (
        text
        .decode('unicode-escape')  # \u00fc -> ü
        .encode('utf-8')
        .decode('string_escape')  # \x -> x
    )

    # text = text.decode('unicode-escape')  # \u00fc -> ü
    # h = HTMLParser()
    # text = h.unescape(text)  # &quot; -> "
    # text = text.encode('utf-8')
    # text = text.decode('string_escape')  # \" -> "

    text = text.replace('\/', '/')

    return text


def get_bundesland(bundesland):
    # --------------------------------------------------------------------------------------------------------------------------------------
    # Get the ids of the issues:

    # httrack -S −p1 http://tvthek.orf.at/vorarlbergheute

    bundesland_heute_url = 'https://tvthek.orf.at/%sheute' % bundesland

    needle = 'https:\/\/tvthek\.orf\.at\/profile\/%s-heute\/(?P<id>\d*)' % bundesland
    ids = get_html(url=bundesland_heute_url, needle=needle)

    try:
        id = ids[0]
    except IndexError:
        print ('Error: id %s not found.' % id)

    print ('id: %s' % id)

    # --------------------------------------------------------------------------------------------------------------------------------------
    # Get the region_title:

    issue_url = 'https://tvthek.orf.at/profile/%s-heute/%s' % (bundesland, id)
    print ('issue_url: %s' % issue_url)

    needle = '<title>(?P<id>.*)<\/title>'
    region_title = get_html(url=issue_url, needle=needle)
    try:
        region_title = region_title[0]
    except IndexError:
        print("Title not found.")

    print ('region_title: %s' % region_title)

    region_title = '<h1><a href="%s">%s</a></h1>' % (issue_url, region_title)

    # --------------------------------------------------------------------------------------------------------------------------------------
    # Get the links to the articles:

    # URL: https://tvthek.orf.at/profile/Vorarlberg-heute/70024/Vorarlberg-heute/14007984/Bus-in-Vollbrand/14466163
    # Regex: value=\"https:\/\/tvthek\.orf\.at\/profile\/Vorarlberg-heute\/70024\/Vorarlberg-heute\/\d*\/[\dA-Za-z\-]*\/\d*

    needle = 'value=\"(?P<url>https:\/\/tvthek\.orf\.at\/profile\/%s-heute\/%s\/%s-heute\/\d*\/[\dA-Za-z\-]*\/\d*)' % (
        bundesland, id, bundesland)

    links = get_html(
        url=issue_url,
        needle=needle,
        start_identifier='b-player-segments',
        end_identifier='b-video-details'
    )

    if len(links) == 0:
        raise Exception("Links could not be extracted.")

    # --------------------------------------------------------------------------------------------------------------------------------------
    # Get the texts

    # title&quot;:&quot;Relaunch der ORF-TVthek&quot;
    # ,&quot;description&quot;:&quot;Mit dem Relaunch bietet die ORF-TVthek ein komplett neues Erscheinungsbild. Das Design passt sich an das jeweilige Endger\u00e4t an. Zudem erleichtern viele neue Features die Handhabung.
    # &quot;,

    # How to match “anything up until this sequence of characters” in a regular expression?
    # https://stackoverflow.com/questions/7124778/how-to-match-anything-up-until-this-sequence-of-characters-in-a-regular-expres

    # needle = 'title&quot;:&quot;.+?(?=&quot;duration&quot;)'
    needle = '&quot;,&quot;title&quot;:&quot;(?P<title>.+?)(?=&quot;,&quot;description&quot;)&quot;,&quot;description&quot;:(?P<description>.+?)(?=,&quot;duration&quot;)'

    texts = get_html(
        url=issue_url,
        needle=needle,
        start_identifier='jsb_VideoPlaylist',
        end_identifier='jsb_Tracker/NuragoTracker'
    )
    # start_identifier until 06.03.2021: <div class="b-player-controls jsb_VideoControls"
    # end_identifier until 29.07.2019: <div class="timeline-wrapper js-timeline-wrapper ">

    # TODO: Vorarlberg heute","mode":"vod","preview_image_url":"https://api-tvthek.orf.at/uploads/media/segments/0116/53/thumb_11552507_segments_player.jpeg","growing":true,"segments_complete":true,"duration_in_seconds":1093.475,"transcription_url":,"is_gapless":true,"has_livestream":true,"is_livestream_over":true,"videos":[{"id":14874430,"episode_id":14084230,"title_prefix":"","title_separator":"|","title":"Signation | Themen
    # Sollte eigentlich "Signation | Themen" sein

    body = ''
    topic = 0

    print("Links:\n{}".format('\n'.join(links)))
    print("The length of list is: {}".format(len(links)))
    # print("Texts {}".format(texts))

    for text in texts:
        highlight = False
        title = decode_js_text(text[0])
        print('\n')
        print('-' * 80)
        print("Title: {}".format(title))
        description = decode_js_text(text[1])
        description = description[1:-1]  # Remove the quotes "..."
        print("Description: {}".format(description))

        found_keywords = []

        for keyword in KEYWORDS:
            if keyword.lower() in description.lower():
                print(
                    "Found keyword “{keyword}” in description “{description}”."
                    .format(
                        keyword=keyword.lower(),
                        description=description.lower(),
                    )
                )
                description = '<span style="font-weight: bold; color: OrangeRed;">%s</span>' % description
                highlight = True
                found_keywords.append(keyword)

        if found_keywords:
            description = '%s<br />[found keywords: %s]' % (description, ', '.join(found_keywords))

        description = '<p style="font-size: 14px;">%s</p>' % (description)

        content = ''
        try:
            link = links[topic]
            content = '<a href="%s"><h2>%s</h2></a><p>%s</p>' % (link, title, description)
        except IndexError:
            pass

        if highlight:
            highlights.append(content)
            highlights.append(region_title)

        body = '%s%s' % (body, content)
        topic = topic + 1

    body = '<br /><hr />%s%s' % (region_title, body)

    # print("Body: {}".format(body))
    return body


def send_mail(body):
    # http://stackoverflow.com/questions/882712/sending-html-email-using-python

    # Create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')
    msg['Subject'] = "Bundesland Heute %s" % date.today().strftime("%d.%m.%Y")
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO

    # Record the MIME types of both parts - text/plain and text/html.
    part2 = MIMEText(body, 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(part2)

    # Send the message via local SMTP server.
    s = smtplib.SMTP(SMTP_SERVER)
    s.login(SMTP_USER, SMTP_PASSWORD)
    # sendmail function takes 3 arguments: sender's address, recipient's address
    # and message to send - here it is sent as one string.
    s.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    s.quit()

# ------------------------------------------------------------------------------------------------------------------------------------------


bundeslaender = [
    'Vorarlberg',
    'Niederoesterreich',
    'Tirol',
    'Suedtirol',
    'Steiermark',
    'Kaernten',

    'Burgenland',
    'Oberoesterreich',
    'Salzburg',
    'Wien',
]

body = ''

for bundesland in bundeslaender:
    print('\n')
    print('▒' * 80)
    print(bundesland)
    bundesland_body = get_bundesland(bundesland)
    body = '%s%s' % (body, bundesland_body)

for highlight in highlights:
    body = '%s<br />%s' % (highlight, body)

if highlights:
    body = '<h1>Highlights</h1><hr>%s' % body

send_mail(body)
