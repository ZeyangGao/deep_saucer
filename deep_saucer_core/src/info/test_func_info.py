# -*- coding: utf-8 -*-
#******************************************************************************************
# Copyright (c) 2019
# School of Electronics and Computer Science, University of Southampton and Hitachi, Ltd.
# All rights reserved. This program and the accompanying materials are made available under
# the terms of the MIT License which accompanies this distribution, and is available at
# https://opensource.org/licenses/mit-license.php
#
# March 1st, 2019 : First version.
#******************************************************************************************
import os
from collections import OrderedDict

import yaml

from conf.configuration import TEST_FUNC, ID, PATH, UTF8, ENV_SETUP, CONF_PATH
from src.info.base_info import BaseData


class TestFuncInfo(object):
    __data_dict = {}

    @classmethod
    def read_conf(cls, file_path=''):
        # read config
        try:
            with open(file=file_path, mode='r', encoding=UTF8) as read_file:
                load_val = yaml.load(read_file)
                if load_val and TEST_FUNC in load_val:
                    for val in load_val[TEST_FUNC]:
                        test_func = TestFunc(identifier=val[ID], path=val[PATH],
                                             env_id=val[ENV_SETUP],
                                             conf_path=val[CONF_PATH])

                        cls.add_data(test_func)

        except Exception as e:
            print(e)
            return False

        return True

    @classmethod
    def data(cls):
        data_list = []

        for identifier, test_func in cls.data_items():
            data_list.append(OrderedDict(
                {ID: test_func.id, PATH: test_func.path,
                 ENV_SETUP: test_func.env_id, CONF_PATH: test_func.conf_path}))

        return {TEST_FUNC: data_list}

    @classmethod
    def data_items(cls):
        return cls.__data_dict.items()

    @classmethod
    def data_values(cls):
        return cls.__data_dict.values()

    @classmethod
    def max_id(cls):
        if len(cls.__data_dict) == 0:
            return -1
        return max(cls.__data_dict.keys())

    @classmethod
    def get_data(cls, key):
        if key not in cls.__data_dict.keys():
            return None
        else:
            return cls.__data_dict[key]

    @classmethod
    def get_data_with_path(cls, path):
        values = [value for value in cls.data_values() if
                  value.abs_path == path]
        if len(values) > 0:
            return values[0]
        else:
            return None

    @classmethod
    def get_data_with_name(cls, name):
        try:
            data = next(filter(
                lambda d: d.name_key == name,
                cls.data_values()))
            return data

        except StopIteration:
            return None

    @classmethod
    def add_data(cls, value):
        if value.id not in cls.__data_dict.keys():
            cls.__data_dict[value.id] = value
            return True
        else:
            return False

    @classmethod
    def delete_data(cls, index):
        if type(index) is not list:
            if index is cls.max_id():
                del cls.__data_dict[index]

            else:
                for i in range(len(cls.data_items()) - 1):
                    if i < index:
                        continue

                    cls.__data_dict[i] = cls.__data_dict[i + 1]
                    cls.__data_dict[i].id = i
                del cls.__data_dict[cls.max_id()]
        else:
            for i in index:
                cls.delete_data(i)


class TestFunc(BaseData):

    def __init__(self, path, env_id, conf_path=None, identifier=None):
        if identifier is None:
            identifier = TestFuncInfo.max_id() + 1

        BaseData.__init__(self, identifier=identifier, path=path)

        if not isinstance(env_id, list):
            self.__env_id = [env_id]
        else:
            self.__env_id = sorted(env_id)

        if conf_path:
            self.__conf_path = conf_path
        else:
            self.conf_path = ''

    @property
    def data_tuple(self):
        return self._id, self.__env_id, self.name, self.abs_path

    @property
    def env_id(self):
        return self.__env_id

    @env_id.setter
    def env_id(self, value):
        self.__env_id = value

    @env_id.deleter
    def env_id(self):
        del self.__env_id

    @property
    def env_key(self):
        return 'env%d' % self.__env_id

    @property
    def name_key(self):
        name_key, _ = os.path.splitext(self.name)
        return name_key

    @property
    def conf_path(self):
        return self.__conf_path

    @conf_path.setter
    def conf_path(self, value):
        self.__conf_path = value

    @conf_path.deleter
    def conf_path(self):
        del self.__conf_path
