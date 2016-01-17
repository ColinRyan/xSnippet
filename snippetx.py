import mmap
import os
import os.path
import pprint
import re
import sublime
import sublime_plugin
import xml.etree.ElementTree as ET


class snippetxCommand(sublime_plugin.TextCommand):

    def getFields(self, lines):
        for line in lines:
            # result_line = line.split(",")  # origin code

            # for escape comma feature START
            result_line = []
            while True:
                r = re.search(r'[^\\](,)', line)
                if r:
                    field = line[:r.end()-1]
                    field = field.replace('\\,', ',')
                    result_line.append(field)
                    line = line[r.end():]
                else:
                    result_line.append(line.replace('\\,', ','))
                    break
            # for escape comma feature END

            yield result_line

    def findFiles(self, path, type=".sublime-snippet"):
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(type):
                    yield os.path.join(root, file)

    def matchFile(self, path, pattern):
        f = open(path)
        s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        if s.find(pattern.encode('utf-8')) != -1:
            return path
        return None

    def readFile(self, path):
        f = open(path)
        s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)       
        return s.read(s.size()).decode("utf-8")

    def findSnippetContent(self, snippet):
        return re.search(r'CDATA\[[\n\r]{0,2}(.*?)\]\]', snippet, re.DOTALL).group(1) if snippet else ''

    def zipSnip(self, snippet, content, indent=''):
        for idx, field in enumerate(content):
            snippet = re.sub(r'(?<!\\)\${{{0}:.*?}}|\${0}'.format(str(idx+1)) ,field, snippet)
        snippet = re.sub(r'(?<!\\)\$\{\d+:(.+?)\}', '\\1', snippet)
        snippet = re.sub(r'(?<!\\)\$\d+', '', snippet)
        return indent + snippet

    def getMatch(self, view, pattern, num):
        return view.substr(view.find(pattern, num))

    def getScope(self, snippet):
        snippet_xml_root_node = ET.fromstring(snippet)
        scope = snippet_xml_root_node.find('scope')
        if scope:
            return scope.text

    def removeNegativeScope(self, scope):
        return re.sub(r'- .*? ', '', scope)

    def checkScope(self, present, allowed):
        for scope in present:
            for allow in allowed:
                if re.match(r'' + scope + r'', allow):
                    return True
        return False

    def filterByScope(self, snippet, allowed):
        scope = {
            'text': self.getScope(snippet),
        }

        print('scope:', end=' ')
        pprint.pprint(scope)

        if scope['text']:
            scope['rmNeg'] = self.removeNegativeScope(scope['text'])

            if self.checkScope(scope['rmNeg'].split(' '), allowed):
                return snippet
            else:
                return None

        else:
            return snippet

    def getData(self, patterns):

        data = {}

        data['+metaRegion']     = self.view.find(patterns['+metaRegion'], 0)

        data['asString']        = self.getMatch(self.view, patterns['+metaRegion'], 0)

        data['asLines']         = data['asString'].splitlines()

        if (re.search(r'sx:', data['asLines'][0])):
            data['snippetName']     = re.search(r'(?<=sx:).+', data['asLines'].pop(0)).group(0)
        elif (re.search(r'sx:', data['asLines'][-1])):
            data['snippetName']     = re.search(r'(?<=sx:).+', data['asLines'].pop(-1)).group(0)
        else: data['snippetName'] = ''

        data['indent']          = re.search(r'[\t ]*', data['asLines'][0]).group(0)

        data['asLinesMassaged'] = [
            re.sub(r'(^[\t ]*|["]*)*', '', content)
            for content in data['asLines'] if content.strip()
        ]

        return data

    def getSnippet(self, name=None, scope=['text.plain']):

        snippet = {}

        snippet['scope']             = [re.sub(r'[\r\n ]*', '', x) for x in scope if x]

        snippet['name']              = name

        snippet['match']             = '<tabTrigger>' + snippet['name'] + '</tabTrigger>'

        snippet['filenames']         = list(self.findFiles(sublime.packages_path()))

        snippet['matchedFilesByTab'] = [self.matchFile(x, snippet['match']) for x in snippet['filenames'] if x]

        snippet['text']              = [self.readFile(x) for x in snippet['matchedFilesByTab'] if x]

        snippet['filteredText']      = list(filter(None.__ne__, snippet['text']  ))     

        snippet['filteredFilesByScope'] = [self.filterByScope(x, scope) for x in snippet['filteredText'] if x]      


        snippet['asString']         = [self.findSnippetContent(x) for x in snippet['filteredFilesByScope'] if x]

        snippet['asStringMassaged'] = [re.sub(r'[\r]', '', content) for content in snippet['asString']]

        return snippet

    def run(self, edit):

        patterns = {'+metaRegion': r"([\t ]*sx:.*[\n\r]*)(.+[\n\r]?)*|(?<=[\n\r])?(.+[\n\r])+([\t ]*sx:.+)" }

        data = self.getData(patterns)

        if (data['+metaRegion'].a >= 0 and data['+metaRegion'].b > 0):
            scope   = self.view.scope_name(data['+metaRegion'].a).split(' ')
            print("self.view.scope_name(data['+metaRegion'].a).split(' '):", end=' ')
            pprint.pprint(self.view.scope_name(data['+metaRegion'].a).split(' '))
            snippet = self.getSnippet(data['snippetName'], scope)
            print("snippet:", end=' ')
            pprint.pprint(snippet)
            if (len(snippet['asStringMassaged'])):
                self.view.replace(edit, data['+metaRegion'], '')

                for snippet in snippet['asStringMassaged']:
                    snips = ''
                    for fields in self.getFields(data['asLinesMassaged']):
                        snips += self.zipSnip(snippet,fields, data['indent'])
                    self.view.insert(edit, data['+metaRegion'].a, snips)
            else:
                sublime.status_message("Can't find snippet named " + snippet['name'])
        else:
            sublime.status_message("Can't find region.")
