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
import urllib2
import urllib
import cookielib
import util
from provider import ContentProvider
from bs4 import BeautifulSoup
import urlparse
import cgi
import re


class TeeveeContentProvider(ContentProvider):
    urls = {'Filmy': 'http://www.filmy.teevee.sk', 'Seriály': 'http://www.teevee.sk'}

    def __init__(self, username=None, password=None, filter=None, tmp_dir='.'):
        ContentProvider.__init__(self, 'teevee.sk', 'http://www.teevee.sk', username, password, filter)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.LWPCookieJar()))
        urllib2.install_opener(opener)

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
        return BeautifulSoup(util.request(url))

    def search(self, keyword):
        result = []
        for category in self.urls.keys():
            for element in self.parse(self.urls[category] + '/ajax/_search_engine.php?search=' +
                    urllib.quote_plus(keyword) + ('&film=1' if category == 'Filmy' else '')).find_all('a'):
                if element.get('href') is not None:
                    item = self.video_item()
                    item['title'] = element.text
                    item['url'] = element.get('href')
                    result.append(item)
        return result

    def list(self, url):
        if '.filmy.' in url:
            if url.count('&') == 0:
                return self.list_movies(url + '/ajax/_filmTable.php?showmore=1&strana=1')
            return self.list_movies(url)
        else:
            if url.count('/') == 2:
                return self.list_series(url + '/ajax/_serials_list.php')
            elif url.count('/') == 4 and url.count('&') == 0:
                return self.list_seasons(url)
            return self.list_episodes(url)

    def list_movies(self, url):
        result = []
        for movie in self.parse(url).find_all('a'):
            date = movie.find('span', 'date')
            if date is not None:
                date.extract()
            item = self.video_item()
            item['title'] = movie.text + (' ' + date.text if date is not None else '')
            item['url'] = movie.get('href')
            result.append(item)
        params = urlparse.parse_qs(urlparse.urlparse(url).query)
        parts = list(urlparse.urlsplit(url))
        d = dict(cgi.parse_qsl(parts[3]))
        d.update(strana=(str(int(params['strana'][0]) + 1) if 'strana' in params else '1'))
        parts[3] = urllib.urlencode(d)
        url = urlparse.urlunsplit(parts)
        if len(self.parse(url).select('a > span')) > 0:
            item = self.dir_item()
            item['type'] = 'next'
            item['url'] = url
            result.append(item)
        return result

    def list_series(self, url):
        result = []
        for series in self.parse(url).select('table > tr > td > a'):
            item = self.dir_item()
            item['title'] = series.text
            item['url'] = url + '?serial_id=' + series.get('href').split('/')[-1]
            result.append(item)
        return result

    def list_seasons(self, url):
        result = []
        for season in self.parse(url).select('.se > a'):
            item = self.dir_item()
            item['title'] = season.text
            item['url'] = url + '&seria_id=' + re.match(r'ShowList\([\d\s]+,\s*\'[^\']+\'\s*,\s*(\d+)\s*\)',
                                                        season.get('onclick')).group(1)
            result.append(item)
        return result

    def list_episodes(self, url):
        result = []
        for serie in self.parse(url).select('.list > .cols > a'):
            item = self.video_item()
            item['title'] = serie.text
            item['url'] = serie.get('href')
            result.append(item)
        return result

    def resolve(self, item, captcha_cb=None, select_cb=None):
        streams = []
        for server in self.parse(item['url']).select('#menuServers > a'):
            base_url = '/'.join(item['url'].split('/')[:3])
            tree = self.parse(base_url + '/ajax/_change_page.php?stav=changeserver&server_id=' +
                              server.get('href').strip('#') + ('&film=1' if '.filmy.' in base_url else ''))
            for stream in tree.find_all(['embed', 'object', 'iframe']):
                src = stream.get('src')
                if src:
                    streams.append(src)
                data = stream.get('data')
                if data:
                    streams.append(data)
        result = self.findstreams('\n'.join(streams), ['(?P<url>[^\n]+)'])
        if len(result) == 1:
            return result[0]
        elif len(result) > 1:
            return select_cb(result)
        return None
