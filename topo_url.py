from PIL import Image
import argparse
import math
import requests
import shutil
import re
import os

DIR = os.path.dirname(os.path.realpath(__file__))

parser = argparse.ArgumentParser(
    description="Builds a topo map by scraping https://www.topoquest.com/")
parser.add_argument('-s', '--skip-download', action='store_true')

args = parser.parse_args()

def frange(x, y, step=1):
    while x < y:
        yield x
        x += step

def merge_images(num_tiles, filenames, file_dest):
    """Merge two images into one, displayed side by side
    :param file1: path to first image file
    :param file2: path to second image file
    :return: the merged Image object
    """
    tot_width = 0
    tot_height = 0
    num_tiles_per_axis = int(math.sqrt(num_tiles))
    tile_images = []
    for x in range(num_tiles_per_axis):
        for y in range(num_tiles_per_axis):
            filename = filenames[x + y * num_tiles_per_axis]
            image = Image.open(filename)

            # append a tuple of top left corner and image object
            (width, height) = image.size
            tile_images.append((width * x, height * y, image))

    # We assume each image is the same size
    tot_width = width * num_tiles_per_axis
    tot_height = height * num_tiles_per_axis

    result = Image.new('RGB', (tot_width, tot_height))
    for corner_x, corner_y, image in tile_images:
        result.paste(im=image, box=(corner_x, corner_y))

    result.save(file_dest)

# Scale constants
original_scale = 16
new_scale = 4
# distance between top/bottom, left/right edges - should be calculated off
# of original_scale, which is meters per pixel. To do this we need to convert
# pixels of the image of the size given (xl right now) to meters, and convert
# that to lat/lon. Check out:
# https://stackoverflow.com/questions/639695/how-to-convert-latitude-or-longitude-to-meters
lat_delta = 0.09179 * 2
lon_delta = 0.13361 * 2

# Input centroid
original_lat = 46.81740
original_lon = -116.87315

# Number of steps we need to take across the map
# lat/lon are centroids, so offset each by .5
scale_mult = original_scale / new_scale
step_start = scale_mult / 2 - scale_mult + 0.5
step_end = scale_mult - scale_mult / 2 + 0.5
num_steps = scale_mult * scale_mult

lat_step = lat_delta / scale_mult
lon_step = lon_delta / scale_mult

domain = 'https://www.topoquest.com'
template = domain + '/map.php?lat={}&lon={}&datum=nad27&zoom=4&map=auto&coord=d&mode=zoomin&size=xl'
tiles_dir = os.path.join(DIR, 'tiles')

if args.skip_download:
    image_filenames = [
        os.path.join(tiles_dir, image_name) for image_name
        in sorted(os.listdir(tiles_dir))
        if image_name.endswith('.jpg')
    ]
else:
    urls = []
    for lat_frame in frange(step_start, step_end):
        for lon_frame in frange(step_start, step_end):
            # Subtract lat since we're starting from top; add lon since we're
            # moving left to right
            cur_lat = original_lat - lat_step * lat_frame
            cur_lon = original_lon + lon_step * lon_frame

            urls.append(template.format(cur_lat, cur_lon))

    # Make sure the directory exists, remove everything in there
    shutil.rmtree(tiles_dir)
    os.makedirs(tiles_dir)

    image_names = []
    regex = r'<input name="ref" type="image" src="(.+)" border="0">'
    for idx, url in enumerate(urls):
        print("Requesting tile {} of {}".format(idx + 1, num_steps))

        res = requests.get(url)
        match = re.search(regex, res.text)
        image_names.append(match.group(1))

    image_filenames = []
    for idx, image_name in enumerate(image_names):
        print("Fetching tile {} of {}".format(idx + 1, num_steps))

        res = requests.get(domain + image_name, stream=True)
        filepath = os.path.join(tiles_dir, "{}.jpg".format(idx))
        image_filenames.append(filepath)

        with open(filepath, 'wb') as f:
            for chunk in res:
                f.write(chunk)

merge_images(num_steps, image_filenames, os.path.join(tiles_dir, 'result.jpg'))
