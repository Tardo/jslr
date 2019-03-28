#!/usr/bin/python
# JS Library Report v0.2.0
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
from multiprocessing import Pool

REPORT_FILENAME = 'report.html'
MAX_WORKERS = 4


def get_lib_name(filename):
    ms = re.search(r'([a-z-_\s\.]+[a-z])', filename.lower())
    return ms and ms[1].replace('.js', '') or False


def get_lib_version(filepath):
    files = filepath.split('/')
    ms = re.search(r'[-_](\d{1,2}\.\d{1,2}\.\d{1,3})', files[-1])
    if not ms:
        ms = re.search(r'[-_](\d{1,2}\.\d{1,2})', files[-1])
    if not ms:
        with open(filepath) as file:
            for line in file:
                ms = re.search(r'(?:ver.+[\'"](\d{1,2}\.\d{1,2}\.\d{1,3})|(?:\/\*|\/\/|\*)[^\d]+\sv?(\d{1,2}\.\d{1,2}\.\d{1,3})\s)', line)
                if ms:
                    break
                ms = re.search(r'(?:ver.+[\'"](\d{1,2}\.\d{1,2})|(?:\/\*|\/\/|\*)[^\d]+\sv?(\d{1,2}\.\d{1,2})\s)', line)
                if ms:
                    break
    return ms and (ms[1] or ms[2]) or False


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


def download_cdnjs(index, jslib, to_folder):
    r = urllib.request.urlopen('https://api.cdnjs.com/libraries?search=%s&fields=name,filename,version,homepage,license' % jslib['name'])
    encoding = r.info().get_content_charset('utf-8')
    JSON_object = json.loads(r.read().decode(encoding))
    if any(JSON_object) and any(JSON_object['results']):
        cdnjs_info = JSON_object['results'][0]
        smatch = difflib.SequenceMatcher(
            None,
            get_lib_name(cdnjs_info['name']) or '',
            jslib['name'] or '')
        if not smatch or smatch.quick_ratio() < 0.9:
            print("!", end='', flush=True)
            return False
        result = {}
        if cdnjs_info['version'] > jslib['version']:
            result.update({'new_version': cdnjs_info['version']})
        cdnjs_url = cdnjs_info['latest']
        if not re.search(r'[\.\/\-_]min', jslib['filepath'].split('/')[-1]):
            cdnjs_url = re.sub(r'[\.\/\-_]min', '', cdnjs_url)
        result.update({
            'cdnjs_latest': cdnjs_url,
            'homepage': cdnjs_info['homepage'],
            'license': cdnjs_info['license'],
        })
        cdnjs_url = cdnjs_url.replace(cdnjs_info['version'],
                                      jslib['version'])
        try:
            urllib.request.urlretrieve(cdnjs_url,
                                       '%s/%s.js' % (to_folder, jslib['name']))
        except urllib.error.HTTPError:
            print("!", end='', flush=True)
        else:
            result.update({'cdnjs': cdnjs_url})
            print(".", end="", flush=True)
            return {
                'id': index,
                'result': result,
            }
    return False


def generate_jslib_html_section(jslib, orig_folder):
    if 'new_version' in jslib:
        adv_class = 'warn'
        last_version = '%s <b>NEW VERSION!</b> <a href="%s">Download</a>' % (
            jslib['new_version'], jslib['cdnjs_latest'])
    else:
        adv_class = ''
        last_version = jslib['version']
    tofile = jslib['filepath']
    fromfile = os.path.join(orig_folder, '%s.js' % jslib['name'])
    if filecmp.cmp(fromfile, tofile):
        match_result = "OK"
        diff_html = ''
    else:
        try:
            with open(fromfile) as tfile:
                fromlines = tfile.readlines()
            with open(tofile) as tfile:
                tolines = tfile.readlines()
        except UnicodeDecodeError:
            return '''
                <div class='js_lib err'>
                    <div class='title'>%s <span class='version'>%s</span></div>
                    <div class='last_version'>Lastest Version: %s</div>
                    <div class='homepage'>Homepage: <a href='%s'>%s</a></div>
                    <div class='license'>License: %s</div>
                    <div class='cdnjs'>CDNjs: <a href='%s'>%s</a></div>
                    <div class='hashes'>Files Comparison: ERROR</div>
                    <div class='failure'>Can't read file. Unsupported enconding!</div>
                </div>
            ''' % (
                jslib['filepath'], jslib['version'],
                last_version,
                jslib['homepage'], jslib['homepage'],
                jslib['license'],
                jslib['cdnjs'], jslib['cdnjs'],
            )
        adv_class = 'err'
        match_result = "<span class='failure'>FAIL</span>"
        diff_gen = difflib.HtmlDiff()
        diff_gen._legend = ""
        diff_html = diff_gen.make_table(
            fromlines, tolines, fromfile, tofile, True, 3)
    print(".", end='', flush=True)
    return '''
        <div class='js_lib %s'>
            <div class='title'>%s <span class='version'>%s</span></div>
            <div class='last_version'>Lastest Version: %s</div>
            <div class='homepage'>Homepage: <a href='%s'>%s</a></div>
            <div class='license'>License: %s</div>
            <div class='cdnjs'>CDNjs: <a href='%s'>%s</a></div>
            <div class='hashes'>Files Comparison: %s</div>
            <div class='detail'>%s</div>
        </div>
    ''' % (
        adv_class,
        jslib['filepath'], jslib['version'],
        last_version,
        jslib['homepage'], jslib['homepage'],
        jslib['license'],
        jslib['cdnjs'], jslib['cdnjs'],
        match_result,
        diff_html,
    )


def check_jslibs_integrity(js_libs, orig_folder):
    pool = Pool(processes=MAX_WORKERS)

    # Download JS from CDNjs
    args = [(k, v, orig_folder) for k, v in enumerate(js_libs)]
    result = pool.starmap(download_cdnjs, args)
    for r in result:
        if r:
            js_libs[r['id']].update(r['result'])
    print(" ")

    # Generate HTML
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
                            background-color: white;
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

                        %s
                    </style>
                </head>
                <body>
                    <h1>JS Libraries Report (%d Founded)</h1>
        ''' % (difflib.HtmlDiff()._styles, len(js_libs))
        args = []
        for jslib in js_libs:
            if 'cdnjs' in jslib:
                args.append((jslib, orig_folder))
            else:
                html_str += '''
                    <div class='js_lib noversion'>
                        <div class='title'>%s <span class='version'>%s</span></div>
                        <div class='failure'>No version found. Ommited</div>
                    </div>
                ''' % (jslib['filepath'], jslib['version'])
                print("!", end='', flush=True)
        result = pool.starmap(generate_jslib_html_section, args)
        html_str += '\n'.join(result)
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
