# -*- coding: UTF-8 -*-
# /*
# *      Copyright (C) 2012 Lubomir Kucera
# *
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
# */
import urllib
from urllib2 import URLError
import util
from provider import ContentProvider
from bs4 import BeautifulSoup
import urlparse
import re
from copy import deepcopy


class TeeveeContentProvider(ContentProvider):
    urls = {'Filmy': 'http://www.filmy.teevee.sk'}

    def __init__(self, username=None, password=None, filter=None):
        ContentProvider.__init__(self, 'teevee.sk', 'http://www.teevee.sk', username, password, filter)
        util.init_urllib(self.cache)

    def __del__(self):
        util.cache_cookies(self.cache)

    def capabilities(self):
        return ['resolve', 'categories', 'search']

    def categories(self):
        result = []
        for category in self.urls.keys():
            item = self.dir_item()
            item['title'] = category
            item['url'] = self.urls[category]
            result.append(item)
        return result

    def parse(self, url):
        return BeautifulSoup(util.request(url), 'html5lib', from_encoding='utf-8')

    def search(self, keyword):
        result = []
        for name, url in self.urls.items():
            for link in self.parse(url + '/ajax/_search_engine.php?search=' + urllib.quote_plus(
                    keyword) + ('&film=1' if '.filmy.' in url else '')).find_all('a'):
                if link.get('href') is not None:
                    item = self.video_item()
                    item['title'] = link.text
                    item['url'] = link.get('href')
                    result.append(item)
        return result

    def list(self, url):
        if url.count('#') > 0 or url.count('&') > 0:
            return self.list_movies(url)
        return self.list_genres(url)

    def list_genres(self, url):
        result = []
        for option in self.parse(url + '/filmy/').select(
                '#filter_film [name=filterFilm] [name^=category] option'):
            item = self.dir_item()
            item['title'] = option.text if option.text != '-' else 'Všetky'
            item['url'] = url + '#' + option.get('value')
            result.append(item)
        return result

    def list_movies(self, url):
        result = []
        path = ''
        if '#' in url:
            url, category = url.split('#', 1)
            path = '/ajax/_filmTable.php?filterfilm=1' + \
                   ('&filter[category][]=' + category if len(category) > 0 else '') + \
                   '&filter[description]=1&filter[img_show]=1&filter[show_hd]=0&filter[order]=best'
        for date in self.parse(url + path).select('a span.date'):
            link = date.parent
            date.extract()
            if len(link.text) > 0:
                image = link.find_previous('a')
                if image:
                    image = image.find('img')
                plot = link.find_next_sibling('span')
                item = self.video_item()
                item['title'] = link.text + ' ' + date.text
                item['url'] = link.get('href')
                try:
                    item['year'] = int(re.sub(r'\W+', '', date.text))
                except ValueError:
                    pass
                if image:
                    item['img'] = image.get('src')
                if plot:
                    item['plot'] = plot.text.strip(' -')
                result.append(item)
        if 'showmore' not in url:
            url += '/ajax/_filmTable.php?showmore=1&strana=1'
        else:
            params = urlparse.parse_qs(urlparse.urlparse(url).query)
            parts = list(urlparse.urlsplit(url))
            d = dict(urlparse.parse_qsl(parts[3]))
            d.update(strana=(str(int(params['strana'][0]) + 1) if 'strana' in params else '1'))
            parts[3] = urllib.urlencode(d)
            url = urlparse.urlunsplit(parts)
        if len(self.parse(url).select('a span')) > 0:
            item = self.dir_item()
            item['type'] = 'next'
            item['url'] = url
            result.append(item)
        return result

    def resolve(self, item, captcha_cb=None, select_cb=None):
        streams = []

        def find_streams(stream):
            for src in self.parse(stream['url']).find_all(['embed', 'object', 'iframe', 'script']):
                for attribute in ['src', 'data']:
                    value = src.get(attribute)
                    if value:
                        if src.name == 'script' and not value.startswith('data:'):
                            continue
                        new_stream = deepcopy(stream)
                        new_stream['url'] = value
                        streams.append(new_stream)

        for server in self.parse(item['url']).select('#menuServers > a'):
            language = server.find('span', '')
            language = ' %s dabing' % re.sub(r'\W+', '', language.text) if language else ''
            base_url = '/'.join(item['url'].split('/')[:3])
            find_streams({'url': '%s/ajax/_change_page.php?stav=changeserver&server_id=%s%s' %
                                 (base_url, server.get('href').strip('#'),
                                  '&film=1' if '.filmy.' in base_url else ''),
                          'lang': language})
        for stream in streams:
            try:
                find_streams(stream)
            except ValueError:
                pass
            except URLError:
                pass
        result = self.findstreams(streams)
        if len(result) == 1:
            return result[0]
        elif len(result) > 1:
            return select_cb(result)
        return None
