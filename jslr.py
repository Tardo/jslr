#!/usr/bin/python
# JS Library Report
# Copyright 2019 Alexandre Díaz <dev@redneboa.es>
# License GPL-3.0 or later (https://www.gnu.org/licenses/gpl).

import os
import re
import tempfile
import urllib.request
import json
import difflib
import filecmp
import sys

REPORT_FILENAME = 'report.html'


def get_lib_name(filename):
    ms = re.search(r'([a-z-_\s]+[a-z])', filename.lower())
    return ms and ms[1] or False


def get_lib_version(filepath):
    files = filepath.split('/')
    ms = re.search(r'[-_](\d+\.\d+\.\d+)', files[-1])
    if not ms:
        ms = re.search(r'[-_](\d+\.\d+)', files[-1])
    if not ms:
        with open(filepath) as file:
            for line in file:
                ms = re.search(r'\s[v\'"]?(\d+\.\d+\.\d+)', line)
                if ms:
                    break
                ms = re.search(r'\s[v\'"](\d+\.\d+)', line)
                if ms:
                    break
    return ms and ms[1] or False


def get_js_libs(path):
    js_libs = []
    for root, dirs, files in os.walk(path):
        for filename in files:
            if filename.lower().endswith('.js'):
                filepath = os.path.join(root, filename)
                libname = get_lib_name(filename)
                libver = get_lib_version(filepath)
                if libname and libver:
                    js_libs.append({
                        'name': libname,
                        'version': libver,
                        'filepath': filepath,
                    })
    return js_libs


def download_cdnjs(js_libs, to_folder):
    regex_min = r'[\.\/\-_]min'
    for jslib in js_libs:
        r = urllib.request.urlopen('https://api.cdnjs.com/libraries?search=%s&fields=name,filename,version' % jslib['name'])
        encoding = r.info().get_content_charset('utf-8')
        JSON_object = json.loads(r.read().decode(encoding))
        if any(JSON_object) and any(JSON_object['results']):
            cdnjs_info = JSON_object['results'][0]
            if cdnjs_info['version'] > jslib['version']:
                jslib.update({
                    'outdated': True,
                    'new_version': cdnjs_info['version'],
                })
            cdnjs_url = cdnjs_info['latest']
            if not re.search(regex_min, jslib['filepath'].split('/')[-1]):
                cdnjs_url = re.sub(regex_min, '', cdnjs_url)
            jslib.update({'cdnjs_latest': cdnjs_url})
            cdnjs_url = cdnjs_url.replace(cdnjs_info['version'],
                                          jslib['version'])
            try:
                urllib.request.urlretrieve(cdnjs_url,
                                           '%s/%s.js' % (to_folder,
                                                         jslib['name']))
            except urllib.error.HTTPError:
                print("!", end='', flush=True)
                pass
            else:
                jslib.update({'cdnjs': cdnjs_url})
                print(".", end='', flush=True)
    print(" ")


def check_jslibs_integrity(js_libs, orig_folder):
    download_cdnjs(js_libs, orig_folder)

    with open(REPORT_FILENAME, 'w') as file:
        html_str = '''
            <!DOCTYPE html>
            <html lang="en">
                <head>
                    <style>
                        .js_lib {
                            padding: 0.5em;
                            margin: 1em 0;
                            border: 1px solid darkgray;
                            border-radius: 3px;
                            background-color: #e9ffe9;
                        }
                        .js_lib > .title {
                            font-weight: bold;
                            padding: 0.3em;
                            background-color: #44a4c9;
                            border-radius: 3px 3px 0 0;
                        }
                        .js_lib > .title > .version {
                            font-size: xx-large;
                        }

                        .js_lib .failure {
                            color: red;
                        }

                        .js_lib > .detail {
                            max-height: 150px;
                            overflow: auto;
                        }

                        .js_lib.warn > .last_version, .js_lib.noversion {
                            background-color: #fffcc7;
                        }
                        .js_lib.err {
                            background-color: #ffc7c7;
                        }

                        table.diff {
                            width: 100%%;
                        }
                    </style>
                </head>
                <body>
                    <h1>JS Libraries Report (%d Founded)</h1>
        ''' % len(js_libs)
        for jslib in js_libs:
            if 'cdnjs' in jslib:
                if 'outdated' in jslib:
                    adv_class = 'warn'
                    last_version = '%s <b>NEW VERSION!</b> <a href="%s">Download</a>' % (jslib['new_version'], jslib['cdnjs_latest'])
                else:
                    adv_class = ''
                    last_version = jslib['version']
                tofile = jslib['filepath']
                fromfile = os.path.join(orig_folder, '%s.js' % jslib['name'])
                if filecmp.cmp(fromfile, tofile):
                    match_result = "OK"
                    diff_html = ''
                else:
                    with open(fromfile) as tfile:
                        fromlines = tfile.readlines()
                    with open(tofile) as tfile:
                        tolines = tfile.readlines()
                    adv_class = 'err'
                    match_result = "<span class='failure'>FAIL</span>"
                    diff_gen = diff_html = difflib.HtmlDiff()
                    diff_gen._legend = ""
                    diff_html = diff_gen.make_file(
                        fromlines, tolines, fromfile, tofile, True, 3)
                html_str += '''
                    <div class='js_lib %s'>
                        <div class='title'>%s <span class='version'>%s</span></div>
                        <div class='last_version'>Lastest Version: %s</div>
                        <div class='cdnjs'>CDNjs: <a href='%s'>%s</a></div>
                        <div class='hashes'>Files Comparison: %s</div>
                        <div class='detail'>%s</div>
                    </div>
                ''' % (
                    adv_class,
                    jslib['filepath'], jslib['version'],
                    last_version,
                    jslib['cdnjs'], jslib['cdnjs'],
                    match_result,
                    diff_html,
                )
                print(".", end='', flush=True)
            else:
                html_str += '''
                    <div class='js_lib noversion'>
                        <div class='title'>%s <span class='version'>%s</span></div>
                        <div class='failure'>No version found. Ommited</div>
                    </div>
                ''' % (jslib['filepath'], jslib['version'])
                print("!", end='', flush=True)
        html_str += '''
                </body>
            </html>
        '''
        file.write(html_str)
        print(" ")


if __name__ == "__main__":
    search_path = len(sys.argv) > 1 and sys.argv[1] or False
    if not search_path:
        print("No folder has been specified")
        exit(1)
    if not os.path.isdir(search_path):
        print("Invalid folder. '%s' doesn't exists!" % search_path)
        exit(1)

    print("Searching JS libraries in '%s'... " % search_path,
          end="", flush=True)
    js_libs = get_js_libs(search_path)
    print("%d founded." % len(js_libs))
    print("Generating HTML, please wait...")
    check_jslibs_integrity(js_libs, tempfile.mkdtemp())
    print("Task finished successfully")
