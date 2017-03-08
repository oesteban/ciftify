"""
Contains the QC settings dictionary for all cifti_vis scripts, as well as
a class to make access to settings easy to read.
"""
import os
import sys
import logging
from abc import ABCMeta, abstractmethod

import yaml

import ciftify.config as config
from ciftify.utilities import docmd
from ciftify.utilities import TempDir

class Config(object):
    def __init__(self, mode):
        self.__qc_settings = self.__read_mode(mode)
        self.template_name = self.__qc_settings['TemplateFile']
        self.template = self.__get_template()
        self.__scene_dict = self.__get_scene_dict()
        self.__montages = self.__get_montages()
        self.images = self.__get_images()

    def __read_mode(self, mode):
        ciftify_path = os.path.dirname(__file__)
        qc_modes_rel_path = os.path.join(ciftify_path, '../data/qc_modes.yaml')
        qc_settings = os.path.abspath(qc_modes_rel_path)
        try:
            with open(qc_settings, 'r') as qc_stream:
                qc_modes = yaml.load(qc_stream)
        except:
            logging.error("Cannot read qc_modes file: {}".format(qc_settings))
            sys.exit(1)
        try:
            settings = qc_modes[mode]
        except KeyError:
            logging.error("qc_modes file {} does not define mode {}"
                    "".format(qc_settings, mode))
            sys.exit(1)
        return settings

    def __get_template(self):
        template_dir = config.find_scene_templates()
        return os.path.join(template_dir, self.template_name)

    def __get_scene_dict(self):
        """
        Generates a dict to help separate the scenes that are montage only
        from the scenes that appear individually on the page.
        """
        scene_dict = {}
        for scene_type in self.__qc_settings['scene_list']:
            cur_scene = Scene(scene_type)
            scene_dict[cur_scene.name] = cur_scene
        return scene_dict

    def __get_montages(self):
        """
        When montages are made, scenes may be deleted from scene dict
        if they are a member of a montage but not labeled 'Keep'
        """
        montages = []
        for montage_type in self.__qc_settings['montage_list']:
            cur_montage = Montage(montage_type, self.__scene_dict)
            montages.append(cur_montage)
        return montages

    def __get_images(self):
        images = []
        images.extend(self.__montages)
        images.extend(self.__scene_dict.values())
        images = sorted(images, key=lambda image: image.order)
        return images

class QCScene(object):
    """
    This abstract class acts as a base class for both Montage and Image so
    both can be used interchangeably in ciftify-vis scripts.
    """

    __metaclass__ = ABCMeta

    _attributes = {}
    name = ''
    path = ''
    make_index = False
    order = 0

    def _get_attribute(self, key):
        try:
            attribute = self._attributes[key]
        except KeyError:
            logging.error("Scene {} does not contain the key {}. " \
                    "Exiting".format(self._attributes, key))
            sys.exit(1)
        return attribute

    @abstractmethod
    def make_image(self, output_path, scene_file):
        pass

class Scene(QCScene):
    def __init__(self, attributes):
        self._attributes = attributes
        self.name = self._get_attribute('Name')
        self.make_index = self._get_attribute('MakeIndex')
        self.index = self._get_attribute('Idx')
        self.split_horizontal = self._get_attribute('SplitHorizontal')
        self.save_image = self._get_attribute('Keep')
        self.order = self._get_attribute('Order')

    def make_image(self, output_loc, scene_file, logging='WARNING', width=600,
            height=400):
        if self.split_horizontal:
            self.path = self.__split(output_loc, scene_file, logging, width,
                    height)
            return
        self.__show_scene(output_loc, scene_file, logging, width, height)
        self.path = output_loc

    def __show_scene(self, output, scene_file, logging, width, height):
        docmd(['wb_command', '-logging', logging, '-show-scene',
                scene_file, str(self.index), output, width, height])

    def __split(self, output_loc, scene_file, logging, width, height):
        with TempDir() as tmp_dir:
            tmp_img = os.path.join(tmp_dir, "scene{}.png".format(self.index))
            self.__show_scene(tmp_img, scene_file, logging, width, height)

            tmp_top = os.path.join(tmp_dir,'top.png')
            tmp_bottom = os.path.join(tmp_dir,'bottom.png')

            docmd(['convert', tmp_img, '-crop', '100x50%+0+0', tmp_top])
            docmd(['convert', tmp_img, '-crop', '100x50%+0+200', tmp_bottom])
            docmd(['montage', '-mode', 'concatenate', '-tile', '2x1', tmp_top,
                    tmp_bottom, output_loc])
        return output_loc

    def __repr__(self):
        return "<ciftify.qc_config.Scene({})>".format(self.name)

    def __str__(self):
        return self.name

class Montage(QCScene):
    def __init__(self, attributes, scene_dict):
        self._attributes = attributes
        self.name = self._get_attribute('Name')
        self.pics = self._get_attribute('Pics')
        self.layout = self._get_attribute('Layout')
        self.make_index = self._get_attribute('MakeIndex')
        self.scenes = self.__get_scenes(scene_dict)
        self.order = self._get_attribute('Order')

    def __get_scenes(self, scene_dict):
        """
        This method will delete scenes from scene_dict if any are included in
        the montage but not labeled 'Keep'.
        """
        scenes = []
        for pic in self.pics:
            scene = scene_dict[pic]
            if not scene.save_image:
                del scene_dict[pic]
            scenes.append(scene)
        return scenes

    def make_image(self, output_loc, scene_file, logging='WARNING', width=600,
                height=400):
        montage_cmd=['montage', '-mode', 'concatenate', '-tile',
                self.layout]
        with TempDir() as tmp_dir:
            for scene in self.scenes:
                tmp_path = os.path.join(tmp_dir, "{}.png".format(scene.name))
                scene.make_image(tmp_path, scene_file, logging, width, height)
                montage_cmd.append(tmp_path)
            montage_cmd.append(output_loc)
            docmd(montage_cmd)
            self.path = output_loc

    def __repr__(self):
        return "<ciftify.qc_config.Montage({})>".format(self.name)

    def __str__(self):
        return self.name
