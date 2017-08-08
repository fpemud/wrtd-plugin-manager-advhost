#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import json
import signal
import socket
import logging
import pyroute2
import msghole
from gi.repository import Gio
from . import util


def get_plugin_list():
    return ["advhost"]


def get_plugin(name):
    if name == "advhost":
        return _PluginObject()
    else:
        assert False


class _PluginObject:

    def init2(self, cfg, tmpDir, varDir, data):
        self.param = data
        self.logger = logging.getLogger(self.__module__ + "." + self.__class__.__name__)

        # register endpoint factory
        fac = EndPointFactory(self)
        self.param.managers["apiserver"].register_endpoint_factory("advhost", fac)
        self.param.managers["apiserver"].register_endpoint_factory("gwim", fac)

    def dispose(self):
        pass

    def get_router_info(self):
        return dict()


class EndPointFactory:

    def __init__(self, pObj):
        self.pObj = pObj

    def new_endpoint(self, channel, local_ip, local_port, peer_ip, peer_port, sproc):
        if channel == "advhost":
            return AdvHostEndPoint(self.pObj, peer_ip, sproc)
        elif channel == "gwim":
            return GwImEndPoint(self.pObj, peer_ip, sproc)


class AdvHostEndPoint:

    def __init__(self, pObj, peer_ip, sproc):
        self.pObj = pObj
        self.peer_ip = peer_ip
        self.sproc = sproc

    def init2(self, data):
        # send reply
        data2 = dict()
        data2["network-list"] = []
        data2["host-list"] = []
        return data2

    def close2(self):
        pass

    def on_command_get_network_list(self, data, return_callback, error_callback):
        pass

    def on_command_get_host_list(self, data, return_callback, error_callback):
        pass

    def on_command_wakeup(self, data, return_callback, error_callback):
        pass



class GwImEndPoint:

    def __init__(self, pObj, peer_ip, sproc):
        self.pObj = pObj
        self.peer_ip = peer_ip
        self.sproc = sproc
