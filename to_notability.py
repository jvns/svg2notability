import svgpathtools
from collections import namedtuple
import zipfile
import plistlib
import subprocess
import contextlib
import os
import os.path
import tempfile
import numpy as np
import itertools
import struct

Path = namedtuple('Path', 'points attrs')
Attrs = namedtuple('Attrs', 'width color')

# plist methods

def base_notability_file(filename=None):
    base_dir = os.path.dirname(__file__)
    if filename is None:
        filename = os.path.join(base_dir, './template.note')
    return zipfile.ZipFile(filename, 'r')

def base_plist(filename=None):
    temp_dir = tempfile.mkdtemp() # todo: remove dir
    with base_notability_file(filename=filename) as zipf:
        start = os.path.basename(zipf.filename).replace('.note', '')
        if filename is None:
            start = 'reverse'
        extracted_filename = zipf.extract(os.path.join(start,'Session.plist'), temp_dir)
        return plistlib.readPlistFromString(subprocess.check_output(['plistutil', '-i', extracted_filename]))

def create_zip_file(new_name, pl):
    note_filename = '{name}.note'.format(name=new_name)
    temp_dir = tempfile.mkdtemp() # todo: remove dir
    xml_file = os.path.join(temp_dir, 'plist.xml')
    plistlib.writePlist(pl, xml_file)
    with base_notability_file() as zipf:
        zipf.extractall(temp_dir)
    subprocess.check_call(['mv', os.path.join(temp_dir, 'reverse'), os.path.join(temp_dir, new_name) ])
    subprocess.check_output(['plistutil', '-i', xml_file, '-o',  os.path.join(temp_dir, new_name, "Session.plist")])
    with remember_cwd():
        os.chdir(temp_dir)
        subprocess.check_call(['zip', '-r', note_filename, new_name + '/'])
    subprocess.check_call(['mv', os.path.join(temp_dir, note_filename), note_filename ])
    return note_filename

@contextlib.contextmanager
def remember_cwd():
    curdir= os.getcwd()
    try: yield
    finally: os.chdir(curdir)

# converting

CurveProperties = namedtuple('CurveProperties', 'colors width numpoints fractionalwidths points event_tokens count_fracwidths count_curves count_points')

def pack_struct(l, fmt):
    return struct.pack('{num}{format}'.format(num=len(l), format=fmt), *l)

def render_color(hexcode):
    try:
        return struct.pack('>I', int(hexcode.replace('#', '') + 'ff', 16))
    except:
        return '\x00\x00\x00\xff'

def generate_curve_properties(aggregated_paths):
    num_curves = len(aggregated_paths)
    num_points = np.array([len(x.points) for x in aggregated_paths])
    curvesfractionalwidths = np.zeros(sum(np.maximum(num_points / 3 + 1, 2)),  dtype=float) + 1.0
    x_max = max(y.real for x in aggregated_paths for y in x.points)
    x_limit = 450
    scaling = x_limit / x_max
    curveswidths = np.array([float(x.attrs.width) if x.attrs.width is not None else 1.0 for x in aggregated_paths])
    points = np.array(list(itertools.chain(*[[y.real, y.imag] for x in aggregated_paths for y in x.points])))
    colors = ''.join([render_color(x.attrs.color) for x in aggregated_paths])
    return CurveProperties(
        colors=colors,
        width=pack_struct(scaling * curveswidths, 'f'),
        event_tokens = '\xff\xff\xff\xff' * num_curves,
        numpoints=pack_struct(num_points, 'i'),
        fractionalwidths=struct.pack('%sf' % len(curvesfractionalwidths), *curvesfractionalwidths),
        points=pack_struct(scaling * points, 'f'),
        count_fracwidths = len(curvesfractionalwidths),
        count_curves = num_curves,
        count_points = len(points)/2,
    )


def plist_from_aggregated_paths(aggregated_paths, new_name):
    pl = base_plist()
    objects = pl['$objects']
    objects[-8] = new_name
    path_data = objects[8]
    properties = generate_curve_properties(aggregated_paths)
    path_data['curvescolors'] = plistlib.Data(properties.colors)
    path_data['curvespoints'] = plistlib.Data(properties.points)
    path_data['curveswidth'] = plistlib.Data(properties.width)
    path_data['curvesnumpoints'] = plistlib.Data(properties.numpoints)
    path_data['curvesfractionalwidths'] = plistlib.Data(properties.fractionalwidths)
    path_data['eventTokens'] = plistlib.Data(properties.event_tokens)
    objects[9] = properties.count_fracwidths
    objects[10] = properties.count_curves
    objects[11] = properties.count_points
    return pl

# svg parsing methods

def parse_attrs(attrs):
    style = attrs.get('style')
    if style is None:
        return Attrs(color=None, width=None)
    style = dict([x.split(':') for x in style.split(';')])
    return Attrs(color= style.get('stroke'), width = style.get('stroke-width'))

def is_different(prev, current, prev_attrs, current_attrs):
    if prev_attrs != current_attrs:
        return False
    if prev is None:
        return True
    diff = (prev.end - current.start)
    (x,y) = (diff.real, diff.imag)
    return abs(x) < 1e-10 and  abs(y) < 1e-10

def lengthen_path(current_points):
    if len(current_points) < 4 and len(current_points) > 0:
        start = current_points[0]
        end = current_points[-1]
        return [start + 0.01, start + 0.01j] + current_points + [end - 0.01, end - 0.01j]
    return current_points

INTERPOLATE=14
def aggregate_paths(paths):
    prev = None
    all_paths = []
    current_points = []
    current_attrs = Attrs(width=None, color=None)
    for path, attrs in paths:
        attrs = parse_attrs(attrs)
        if is_different(prev, path, current_attrs, attrs):
            for i in range(1, INTERPOLATE+1):
                current_points.append(path.start * (INTERPOLATE-i)/INTERPOLATE + path.end * i/INTERPOLATE)
        else:
            all_paths.append(Path(points=lengthen_path(current_points), attrs=current_attrs))
            if path.start == path.end:
                current_points = [path.start + 0.01, path.start + 0.01j, path.start - 0.01, path.start - 0.01j]
            else:
                current_points = [path.start, path.end] # todo: not right, some paths actually have multiple points *inside* them
            current_attrs = attrs
        prev = path

    all_paths.append(Path(points=lengthen_path(current_points), attrs=current_attrs))
    return all_paths

def get_paths(filename):
    paths, attrs = svgpathtools.svg2paths(filename)
    return zip(paths, attrs)
