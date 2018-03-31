from to_notability import *
import subprocess
import sys
import tempfile
import os.path


def convert(filename):
    tempdir = tempfile.mkdtemp()
    if filename.endswith('svg'):
        svg_filename = filename
    elif filename.endswith('pdf'):
        svg_filename = os.path.join(tempdir, "temp.svg")
        subprocess.check_call(['inkscape', filename, "--export-plain-svg=" + svg_filename])
    new_name = os.path.basename(filename).replace('.pdf', '').replace('.svg', '')
    paths = get_paths(svg_filename)
    aggregated_paths = aggregate_paths(paths)
    aggregated_paths = [x for x in aggregated_paths if len(x.points) >= 1]
    max_y = max((y.imag for x in aggregated_paths for y in x.points))
    reversed_aggregated_paths = [Path(points=[p.real + 1j * (max_y- p.imag) for p in x.points], attrs=x.attrs) for x in aggregated_paths]
    create_zip_file(new_name, plist_from_aggregated_paths(reversed_aggregated_paths, new_name))

if len(sys.argv) < 2:
    print "OH NO"
convert(sys.argv[1])

